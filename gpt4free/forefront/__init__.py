import hashlib
from base64 import b64encode
from json import loads
from re import findall
from time import time, sleep
from typing import Generator, Optional
from uuid import uuid4

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from fake_useragent import UserAgent
from mailgw_temporary_email import Email
from requests import post
from tls_client import Session

from .typing import ForeFrontResponse, AccountData

import requests

class Account:
    @staticmethod
    def create(proxy: Optional[str] = None, logging: bool = False) -> AccountData:
        #proxy='127.0.0.1:33210'
        proxies = {'http': 'http://' + proxy, 'https': 'http://' + proxy} if proxy else False

        start = time()

        mail_client = Email()
        mail_client.register()
        mail_address = mail_client.address

        client = Session(client_identifier='chrome110')
        client.proxies = proxies
        client.headers = {
            'origin': 'https://accounts.forefront.ai',
            'user-agent': UserAgent().random,
        }

        response = client.post(
            'https://clerk.forefront.ai/npm/@clerk/clerk-js@4.39.0/dist/signup_f62107_4.39.0.js',
            #'https://clerk.forefront.ai/v1/client?_clerk_js_version=4.39.0'
            #'https://clerk.forefront.ai/v1/client/sign_ups?_clerk_js_version=4.38.4',
            data={'email_address': mail_address},
        )

        try:
            trace_token = response.json()['response']['id']
            if logging:
                print(trace_token)
        except KeyError:
            raise RuntimeError('Failed to create account!')

        response = client.post(
            f'https://clerk.forefront.ai/v1/client/sign_ups/{trace_token}/prepare_verification?_clerk_js_version=4.38.4',
            data={
                'strategy': 'email_link',
                'redirect_url': 'https://accounts.forefront.ai/sign-up/verify'
            },
        )

        if logging:
            print(response.text)

        if 'sign_up_attempt' not in response.text:
            raise RuntimeError('Failed to create account!')

        while True:
            sleep(5)
            message_id = mail_client.message_list()[0]['id']
            message = mail_client.message(message_id)
            verification_url = findall(r'https:\/\/clerk\.forefront\.ai\/v1\/verify\?token=\w.+', message["text"])[0]
            if verification_url:
                break

        if logging:
            print(verification_url)
        client.get(verification_url)

        response = client.get('https://clerk.forefront.ai/v1/client?_clerk_js_version=4.38.4').json()
        session_data = response['response']['sessions'][0]
        print(session_data)
        user_id = session_data['user']['id']
        print(user_id)
        session_id = session_data['id']
        print(session_id)
        token = session_data['last_active_token']['jwt']
        print(token)
        with open('accounts.txt', 'a') as f:
            f.write(f'{mail_address}:{token}\n')

        if logging:
            print(time() - start)

        return AccountData(token=token, user_id=user_id, session_id=session_id)


class StreamingCompletion:
    @staticmethod
    def create(
        prompt: str,
        account_data: AccountData,
        chat_id=None,
        action_type='new',
        default_persona='607e41fe-95be-497e-8e97-010a59b2e2c0',  # default
        model='gpt-4',
        proxy=None
    ) -> Generator[ForeFrontResponse, None, None]:
        token = account_data.token
        if not chat_id:
            chat_id = str(uuid4())

        proxies = {'http': 'http://' + proxy, 'https': 'http://' + proxy} if proxy else None
        base64_data = b64encode((account_data.user_id + default_persona + chat_id).encode()).decode()
        #print(base64_data)
        encrypted_signature = StreamingCompletion.__encrypt(base64_data, account_data.session_id)

        headers = {
            'authority': 'streaming.tenant-forefront-default.knative.chi.coreweave.com',
            #'authority': 'chat-server.tenant-forefront-default.knative.chi.coreweave.com',
            'accept': '*/*',
            'accept-language': 'en,fr-FR;q=0.9,fr;q=0.8,es-ES;q=0.7,es;q=0.6,en-US;q=0.5,am;q=0.4,de;q=0.3',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://chat.forefront.ai',
            'pragma': 'no-cache',
            'referer': 'https://chat.forefront.ai/',
            'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'authorization': f"Bearer {token}",
            'X-Signature': encrypted_signature,#'dd6cd8e58e560cee2f66fd5d559d077d1db02df5bfe85a59f5835e10813e6d8645b01395c02b3ce8fcf233537370422089a7a302dbe74dbdca20b1904a7f3501',#encrypted_signature,
            'user-agent': UserAgent().random,
        }

        json_data = {
            'text': prompt,
            'action': action_type,
            'parentId': chat_id,
            'workspaceId': chat_id,
            'messagePersona': default_persona,
            'model': model,
        }

        print(headers)
        try:
            response = post(
                'https://streaming.tenant-forefront-default.knative.chi.coreweave.com/chat',
                headers=headers,

            )
            print(response.headers)
            response.raise_for_status()  # Raise an HTTPError if the HTTP request returned an unsuccessful status code.
        except requests.exceptions.RequestException as e:
            # Handle the exception as you see fit.
            print(f"An error occurred: {e}")
        else:
            for chunk in response.iter_lines():
                if b'finish_reason":null' in chunk:
                    data = loads(chunk.decode('utf-8').split('data: ')[1])
                    #print(data)
                    token = data['choices'][0]['delta'].get('content')
                    #print(token)
                    if token is not None:
                        yield ForeFrontResponse(
                            **{
                                'id': chat_id,
                                'object': 'text_completion',
                                'created': int(time()),
                                'text': token,
                                'model': model,
                                'choices': [{'text': token, 'index': 0, 'logprobs': None, 'finish_reason': 'stop'}],
                                'usage': {
                                    'prompt_tokens': len(prompt),
                                    'completion_tokens': len(token),
                                    'total_tokens': len(prompt) + len(token),
                                },
                            }
                        )



        # for chunk in post(
        #     'https://streaming.tenant-forefront-default.knative.chi.coreweave.com/chat',
        #     headers=headers,
        #     proxies=proxies,
        #     json=json_data,
        #     stream=True,
        # ).iter_lines():
        #     if b'finish_reason":null' in chunk:
        #         print(chunk)
        #         data = loads(chunk.decode('utf-8').split('data: ')[1])
        #         #print(data)
        #         token = data['choices'][0]['delta'].get('content')
        #         #print(token)
        #         if token is not None:
        #             yield ForeFrontResponse(
        #                 **{
        #                     'id': chat_id,
        #                     'object': 'text_completion',
        #                     'created': int(time()),
        #                     'text': token,
        #                     'model': model,
        #                     'choices': [{'text': token, 'index': 0, 'logprobs': None, 'finish_reason': 'stop'}],
        #                     'usage': {
        #                         'prompt_tokens': len(prompt),
        #                         'completion_tokens': len(token),
        #                         'total_tokens': len(prompt) + len(token),
        #                     },
        #                 }
        #             )

    @staticmethod
    def __encrypt(data: str, key: str) -> str:
        hash_key = hashlib.sha256(key.encode()).digest()
        iv = get_random_bytes(16)
        cipher = AES.new(hash_key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(StreamingCompletion.__pad_data(data.encode()))
        return iv.hex() + encrypted_data.hex()

    @staticmethod
    def __pad_data(data: bytes) -> bytes:
        block_size = AES.block_size
        padding_size = block_size - len(data) % block_size
        padding = bytes([padding_size] * padding_size)
        return data + padding


class Completion:
    @staticmethod
    def create(
        prompt: str,
        account_data: AccountData,
        chat_id=None,
        action_type='new',
        default_persona='607e41fe-95be-497e-8e97-010a59b2e2c0',  # default
        model='gpt-4',
        proxy=None
    ) -> ForeFrontResponse:
        text = ''
        final_response = None
        #print("----11")  
        for response in StreamingCompletion.create(
            account_data=account_data,
            chat_id=chat_id,
            prompt=prompt,
            action_type=action_type,
            default_persona=default_persona,
            model=model,
            proxy=proxy
        ):
           
            if response:
                final_response = response
                text += response.text
                #print(response)  
        if final_response:
            final_response.text = text
        else:
            raise RuntimeError('Unable to get the response, Please try again')

        return final_response

import os
import sys



sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))

import streamlit as st
from gpt4free import usesless

def get_answer(question: str) -> str:
    try:
        result = usesless.Completion.create(prompt=question)
        #st.write(result) 
        return result["text"]  
        #return result.text
    except Exception as e:
        return (
            f'An error occurred: {e}. Please make sure you are using a valid cloudflare clearance token and user agent.'
        )



# Set page configuration and add header
st.set_page_config(
    page_title="gpt4freeGUI",
    initial_sidebar_state="expanded",
    page_icon="🧠",
    menu_items={
        'Get Help': 'https://github.com/xtekky/gpt4free/blob/main/README.md',
        'Report a bug': "https://github.com/xtekky/gpt4free/issues",
        'About': "### gptfree GUI",
    },
)
st.header('GPT4free GUI')

# Add text area for user input and button to get answer
question_text_area = st.text_area('🤖 Ask Any Question :', placeholder='Explain quantum computing in 50 words')
if st.button('🧠 Think'):
    answer = get_answer(question_text_area)
    # escaped = answer.encode('utf-8').decode('unicode-escape')
    # Display answer
    st.caption("Answer :")
    st.write(answer)
    # st.markdown(escaped)

# Hide Streamlit footer
hide_streamlit_style = """
            <style>
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

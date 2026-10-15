from langchain_openai import ChatOpenAI  
import os  
import httpx  
client = httpx.Client(verify=False) 
llm = ChatOpenAI( 
base_url="https://genailab.tcs.in", 
model = "azure/genailab-maas-gpt-35-turbo", 
api_key="sk-YWIDkTmaJEdmgbu_CH_r0Q", 
http_client = client,
)
llm.invoke("Hi")
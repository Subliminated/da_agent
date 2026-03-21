#%%
#from openai import OpenAI
#import getpass
from dotenv import load_dotenv
import os
import litellm
load_dotenv(dotenv_path='.env',override=True)
import requests
## Load data into-memory
import pandas as pd

#Import the agent class
#%%
from tools import agent_class as llm

#%%

data_path = "data/example.csv"

# Load the CSV data into a DataFrame
df = pd.read_csv(data_path)

# Convert the DataFrame to a CSV string for context injection
df_context = df.to_csv(index=False)

# Add the DataFrame context to the system prompt
# Generate metadata about the CSV file for LLM context

policies = """
AI Policies and Orchestration Rules:

1. Self-Orchestration:
   - The AI must decide whether to answer the user's query directly or generate Python code for data analysis.
   - If the answer can be given without code, respond in clear, concise natural language.
   - If code is required, generate Python code following the guidelines below.

2. Code Generation Guidelines:
   - Use only the following libraries: pandas, numpy, matplotlib, seaborn, openpyxl, scikit-learn.
   - Always start code responses with the tag '#CODE#' on its own line.
   - If the user requests forecasting, use appropriate statistical or machine learning methods (e.g., linear regression, ARIMA, etc.).
   - Include comments in the code to explain key steps if the user requests explanations.
   - Ensure code is executable and does not require user interaction (no input()).

3. Data Handling:
   - Always use the provided CSV data context for analysis.
   - Do not fabricate data or results.
   - If updating or modifying data, clearly indicate changes in the output.

4. Error Handling:
   - If code execution fails, analyze the error and attempt to correct it in subsequent code generations.
   - Do not repeat the same code if it previously failed.
"""

csv_metadata = f"""
The CSV file contains data about various flowers with the following columns:
  "sepal_length": "Length of the sepal in centimeters",
  "sepal_width": "Width of the sepal in centimeters",
  "petal_length": "Length of the petal in centimeters",
  "petal_width": "Width of the petal in centimeters",
  "species": "Species name of the flower (e.g., setosa, versicolor, virginica)",
  "amount": "Amount of the flower in the dataset",   
"""
'(1) If you can answer the query directly (without needing to analyze data), respond to the user in plain text.'
'- A direct answer; or'

SYS_PROMPT = f"""
You are an expert data analyst focused on developing actionable insights. When a user asks a question, do one of the following:

(1) If the query requires you to interrogate or analyze data, or even manipulate data, you must response with Python code only, without any explanations. 
You MUST only use the following libraries: pandas,numpy,matplotlib,seaborn,openpyxl,scikit-learn
At the very start of the code string, add the explicit tag '#CODE#' on its own line. This tag will be used to flag and handle code responses. For example:
#CODE#
print("Hello, World!")

Always return:
- A python code block that includes the #CODE# tag at the start of the code block. No non-executed strings or characters should be included in the response below the code tag
CONTEXT: Any code tagged with '#CODE#' will be executed by the code execution server, which will return the output of the code execution with the tag #CODE EXECUTION RESULTS# at the start as a response.

Here is a sample of the data you will use for analysis which sits in the directory '../data/example.csv':
{df_context}

The CSV file contains data about various flowers with the following columns:
{csv_metadata}
"""

SYS_PROMPT = f"""
You are an expert data analyst focused on developing actionable insights. When a user asks a question, do the following:

Write python code to retrieve the data from the CSV file
You MUST only use the following libraries: pandas,numpy,matplotlib,seaborn,openpyxl,scikit-learn
At the very start of the code string, add the explicit tag '#CODE#' on its own line. This tag will be used to flag and handle code responses. For example:
#CODE#
print("Hello, World!")

Always return:
- A python code block that includes the #CODE# tag at the start of the code block.
- Avoid any explanatory text or comments outside the code block. 
- No non-executed strings or characters should be included in the response below the code tag
Here is a sample of the data you will use for analysis which sits in the directory '../data/example.csv':
{df_context}

The CSV file contains data about various flowers with the following columns:
  "sepal_length": "Length of the sepal in centimeters",
  "sepal_width": "Width of the sepal in centimeters",
  "petal_length": "Length of the petal in centimeters",
  "petal_width": "Width of the petal in centimeters",
  "species": "Species name of the flower (e.g., setosa, versicolor, virginica)",
  "amount": "Amount of the flower in the dataset"
"""
#%%

# %%

### PART 2, Creating a RAG Pipelie
import gradio as gr
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings

#%%
def process_csv(csv_path):
    if csv_path is None:
        return None, None, None

    loader = CSVLoader(file_path=csv_path)
    data = loader.load()

    # Split the documents into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=100
    )
    chunks = text_splitter.split_documents(data)

    embeddings = OllamaEmbeddings(model="llama3:latest")
    
    # Create a vectorstore from the chunks and embeddings
    vectorstore = Chroma.from_documents(
        documents=chunks, embedding=embeddings
        , persist_directory="./chroma_db" # THIS IS THE PERSIST DIRECTORY, UNSET IF YOU DO NOT WANT TO PERSIST THE VECTORSTORE
    )
    # Creates a retriever from the vectorstore
    retriever = vectorstore.as_retriever()

    return text_splitter, vectorstore, retriever 

# If the data already pre-processed, then we just need to load the vectorstore 
def load_vectorstore(persist_directory="./chroma_db"):
    embeddings = OllamaEmbeddings(model="llama3:latest")
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    retriever = vectorstore.as_retriever()
    return vectorstore, retriever

# Create a function to add new documents to the vectorstore
def add_documents_to_vectorstore(docs, vectorstore, persist_directory="./chroma_db"):
    """
    Add new documents to the existing vectorstore and persist it.
    """
    if not docs:
        return vectorstore

    # If docs are LangChain Document objects with 'page_content'
    if hasattr(docs[0], 'page_content'):
        new_docs = [doc.page_content for doc in docs]
    # If docs are dicts with 'page_content'
    elif isinstance(docs[0], dict) and 'page_content' in docs[0]:
        new_docs = [doc['page_content'] for doc in docs]
    else:
        new_docs = [str(doc) for doc in docs]

    # Create a new vectorstore from the new documents
    embeddings = OllamaEmbeddings(model="llama3:latest")
    new_vectorstore = Chroma.from_texts(
        texts=new_docs, embedding=embeddings, persist_directory=persist_directory
    )

    # Merge the new vectorstore with the existing one
    vectorstore.merge(new_vectorstore)

    return vectorstore

def combine_csv_docs(docs):
    """
    Combine a list of LangChain Document objects (from CSV) into a single CSV-like string.
    """
    if not docs:
        return ""
    # If docs are LangChain Document objects with 'page_content'
    if hasattr(docs[0], 'page_content'):
        return "\n".join(doc.page_content for doc in docs)
    # If docs are dicts with 'page_content'
    elif isinstance(docs[0], dict) and 'page_content' in docs[0]:
        return "\n".join(doc['page_content'] for doc in docs)
    # Fallback: just join string representations
    return "\n".join(str(doc) for doc in docs)

#%%

#%%
'''def user_query(prompt, context, model="ollama/llama3:latest"):
    query = f"Question:{prompt}, Context: {context}" #Context is the retrieved RAG data

    messages = [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": query}
    ]
    response = litellm.completion(
        model=model,
        messages=messages,
        api_key=None,  # Most local models do not require an API key
        base_url="http://localhost:11434"  # Change this to your local model's API endpoint
        #max_tokens=512,
        #temperature=0
    )

    code = response['choices'][0]['message']['content']
    return code.strip()'''

# Redefine user_query to use llm instead
def user_query(question, retriever, llm: llm.LiteLLM):
    retrieved_docs = retriever.invoke(question)
    formatted_content = combine_csv_docs(retrieved_docs)

    # Format the question and context for the LLM
    query = f"Question:{question}, Context: {formatted_content}"  # Context is the retrieved RAG data
    #Messages are now handled by the llm instance
    response = llm.generate_response(query)
    return response.strip()

# RAG chain for the context retrieval and response generation
#def rag_chain(question, retriever):
    #retrieved_docs = retriever.invoke(question)
    #formatted_content = combine_csv_docs(retrieved_docs)
    #return user_query(question, formatted_content)

# The following calls the code execution server to run the generated Python code

def code_executor(code: str) -> str:
    response = requests.post("http://localhost:8888/run", json={"code": code})
    if response.ok:
        result = response.json()
        output_str = (
            "=== STDOUT ===\n"
            + result.get("stdout", "").strip()
            + "\n=== STDERR ===\n"
            + result.get("stderr", "").strip()
        )
        #print(output_str)
        return output_str
    else:
        output_str = f"[ERROR] {response.status_code}: {response.text}"
        #print(output_str)
        return output_str

#%%
if __name__ == "__main__":
    user_prompt = SYS_PROMPT + "Can you name all the flowers species in the dataset?"
    user_prompt = SYS_PROMPT + "Can you give me the average sepal length of all the flowers in the dataset?"
    user_prompt = SYS_PROMPT + """Can you predict the species for flowers based on the following data:
    sepal_length,sepal_width,petal_length,petal_width,amount
    5.1,3.5,1.4,0.2,10.5
    """
    #user_prompt = "Can you add 5 new data points to the csv file for me, update the file as well. Please generate the data randomly."

    #user_prompt = input("Please enter your question: ")
    #user_prompt = "Remove the last 5 data points from the csv file for me, update the file as well"

    # Check if vectorstore already exists, if not, process the CSV
    data_path = "data/example.csv"

    if os.path.exists("./chroma_db"):
        print("Loading existing vectorstore...")
        vectorstore, retriever = load_vectorstore()
    else:
        print("Processing CSV file to create vectorstore...")
        # Implement the CSV processing and RAG retrieval, once off
        text_splitter, vectorstore, retriever = process_csv(data_path)
    
    #Setup the LLM instance 
    llm_instance = llm.LiteLLM(model_name="ollama/llama3:latest", system_prompt=SYS_PROMPT)

    #Retrieve context and generate code
    print("Retrieving context and generating code...")
    response = user_query(user_prompt, retriever, llm_instance).strip()

    # First determine if the LLM response contains code or not
    print("\nLLM Response:\n","***\n" ,response,"\n***" )
    results = response
    # Handle the response for the LLM
    #if response.startswith("#CODE#"): 
    if "#CODE#" in response:
        # If the response starts with '#CODE#', it is code to be executed
        print(f"{'#'*50}")
        print("LLM Response contains code, executing it...")
        # Remove the '#CODE#' tag + any explanatory strings and execute the code
        code = response.split("#CODE#", 1)[-1].replace("#CODE#", "").strip()
        execution_result = code_executor(code)
        results = "#CODE EXECUTION RESULTS#\n" + execution_result
        print("\nLLM Response:\n","***\n" ,results, "\n***" )


        counter = 0
        # Whle the results contain an error, send back to llm to re-generate the code
        while "=== STDERR ===" in execution_result and execution_result.split("=== STDERR ===\n")[1].strip():
            print("\nExecution failed, retrying...\n")
            # ASK LLM to re-generate the code with the error in context EDIT: DONT ASK, just send the results back to the llm and it can decide
            response = llm_instance.generate_response(results)
            print("LLM Response:\n", response)

            # Check if the response contains code to be executed
            if not response.startswith("#CODE#"):
                print("LLM did not return code, breaking the loop.")
                break

            # If loop not broken then code was given back, assumed you need to rerun the code execution, so dont need to check if #CODE# tag
            code = response.split("#CODE#", 1)[-1].replace("#CODE#", "").strip() # Remove tag if still present
            execution_result = code_executor(code) # Update the execution results
            results = "#CODE EXECUTION RESULTS#\n" + execution_result
            counter += 1
            if counter > 7:
                print("Max retries reached. Could not get a successful code execution.")
                break

        # Once broken or Code has no errors send the results back to the llm
    response = llm_instance.generate_response(f"Please interpret these results: {results} based on my original question: {user_prompt}")
    print(f"{'#'*50}")
    print("\nFinal LLM Response:\n", response)
    #llm_instance.history.append({"role": "assistant", "content": results})
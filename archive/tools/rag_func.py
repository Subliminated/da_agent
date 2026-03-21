### Creating a RAG Pipelie
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain.schema import Document


#%%
def process_csv(csv_path,rag_db_name=None):
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
        , persist_directory=f"./c{rag_db_name}" # THIS IS THE PERSIST DIRECTORY, UNSET IF YOU DO NOT WANT TO PERSIST THE VECTORSTORE
    )
    # Creates a retriever from the vectorstore
    retriever = vectorstore.as_retriever()

    return text_splitter, vectorstore, retriever 

# Create process_txt function into rag
def process_txt(txt_path,rag_db_name=None):
    if txt_path is None:
        return None, None, None

    with open(txt_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the text into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=100, chunk_overlap=50
    )
    chunks = text_splitter.create_documents([content])

    embeddings = OllamaEmbeddings(model="llama3:latest")
    
    # Create a vectorstore from the chunks and embeddings
    vectorstore = Chroma.from_documents(
        documents=chunks, embedding=embeddings
        , persist_directory=f"./{rag_db_name}" # THIS IS THE PERSIST DIRECTORY, UNSET IF YOU DO NOT WANT TO PERSIST THE VECTORSTORE
    )
    # Creates a retriever from the vectorstore
    retriever = vectorstore.as_retriever()

    return text_splitter, vectorstore, retriever

# If the data already pre-processed, then we just need to load the vectorstore 
def load_vectorstore(persist_directory):
    embeddings = OllamaEmbeddings(model="llama3:latest")
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    retriever = vectorstore.as_retriever()
    return vectorstore, retriever

# Create a function to add new documents to the vectorstore
def add_documents_to_vectorstore(docs, vectorstore):
    """
    Add a text string (or list of strings) as new documents to the existing vectorstore and persist it.
    """
    if not docs:
        return vectorstore

    # If docs is a string, wrap it in a Document
    if isinstance(docs, str):
        docs = [Document(page_content=docs)]
    # If docs is a list of strings, wrap each in a Document
    elif isinstance(docs, list) and isinstance(docs[0], str):
        docs = [Document(page_content=doc) for doc in docs]
    # If docs is already a list of Document objects, do nothing

    # Chunk the new documents into manageable pieces
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=100
    )
    chunks = text_splitter.split_documents(docs)

    vectorstore.add_documents(chunks)

    return vectorstore

def combine_docs(docs):
    """
    Combine a list of LangChain Document objects (from CSV) into a single CSV-like string.
    """
    if not docs:
        return ""
    # If docs are LangChain Document objects with 'page_content'
    if hasattr(docs[0], 'page_content'):
        return "\n".join([doc.page_content for doc in docs])
    # If docs are dicts with 'page_content'
    elif isinstance(docs[0], dict) and 'page_content' in docs[0]:
        return "\n".join([doc['page_content'] for doc in docs])
    # Fallback: just join string representations
    return "\n".join([str(doc) for doc in docs])

# Redefine user_query to use llm instead
def rag_retrieval(question, retriever):
    retrieved_docs = retriever.invoke(question)
    formatted_content = combine_docs(retrieved_docs)
    # Format the question and context for the LLM
    context = f"Question:{question}, Context: \n{formatted_content}"  # Context is the retrieved RAG data
    #Messages are now handled by the llm instance
    return context


#%%
if __name__ == "__main__":
    import os
    data_path = "/Users/gordonlam/Documents/GitHub/NL_to_code/data/documents4rag/job_architecture"
    db_name = "swe_vector_db"  # Name of the vectorstore directory

    if os.path.exists(data_path):
        print("Loading existing vectorstore...")
        vectorstore, retriever = load_vectorstore(f"./{db_name}" )
    else:
        print("Processing document file to create vectorstore...")
        # Implement the document processing and RAG retrieval, once off
        text_splitter, vectorstore, retriever = process_txt(data_path,db_name)

    
    # Read in the datapath into a variable
    with open(data_path, 'r', encoding='utf-8') as f:
        content = f.read()

    #clear a vectorstore of all its documents
    if vectorstore is not None:
        print("Clearing existing vectorstore documents...")
        all_ids = vectorstore.get()['ids']
        vectorstore.delete(ids=all_ids)  # Deletes all documents

    # Add documnents to the vectorstore if needed
    vectorstore = add_documents_to_vectorstore(
        docs = content,
        vectorstore=vectorstore)

    retriever = vectorstore.as_retriever()
    #Retrieve context and generate code
    user_prompt = "I am in the Human Resource Department"
    response = rag_retrieval(user_prompt, retriever)
    print("Retrieved Context:\n", response)
    #print(retriever.invoke(user_prompt))

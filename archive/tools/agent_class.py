from dotenv import load_dotenv
import os
import litellm
load_dotenv(dotenv_path='.env',override=True)

# Models = {
#     "ollama/llama3:latest": "http://localhost:11434",
#     "ollama/mistral:latest": "http://localhost:11434",

# Create wrapers for System, User and Assistant messages
def system_message(content: str) -> dict:
    return {"role": "system", "content": content}
def user_message(content: str) -> dict:
    return {"role": "user", "content": content}
def assistant_message(content: str) -> dict:
    return {"role": "assistant", "content": content}

class LiteLLM:
    def __init__(self, model_name: str = "ollama/llama3:latest", system_prompt: str = "You are a potato", history = None):
        self.model_name = model_name
        #self.api_key = api_key
        #self.system_prompt = system_prompt
        # Assert history is a list of dictionary or else yield value error
        if history is not None and not isinstance(history, list):
            raise ValueError("History must be a list of dictionaries.")
        self.messages = [{"role": "system", "content": system_prompt}] + (history if history else []) 

    def generate_response(self, prompt: str) -> str:
        # Use LLM to generate a response based on the prompt and save to message 
        self.messages.append({"role": "user", "content": prompt})
        response = litellm.completion(
            model=self.model_name,
            messages=self.messages,
            api_key=None,  # Most local models do not require an API key
            base_url="http://localhost:11434")  # Change this to your local model's API endpoint
        
        message = response['choices'][0]['message']['content'].strip()

        # Save LLM response to messages
        self.messages.append({"role": "assistant", "content": message})
        # Return the content of the response
        return message

    def set_model(self, model_name: str):
        self.model_name = model_name

    def set_api_key(self, api_key: str):
        self.api_key = api_key

# Statement LLM call
def generate_response_stateless(prompt: str, model_name: str = "ollama/llama3:latest",sys_prompt = None, history = None) -> str:
    # Use LLM to generate a response based on the prompt and save to message 
    #history.append({"role": "user", "content": prompt})
    message=[{"role": "system", "content": sys_prompt},
         {"role": "user", "content": prompt}]
    response = litellm.completion(
        model=model_name,
        messages=message+(history if history else []) ,
        api_key=None,  # Most local models do not require an API key
        base_url="http://localhost:11434")  # Change this to your local model's API endpoint
    message = response['choices'][0]['message']['content'].strip()
    return message

if __name__ == "__main__":
    # Example usage
    llm = LiteLLM()
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting the chat. Goodbye!")
            break
        response = llm.generate_response(user_input)
        print(f"LLM Response: {response}")

    # Stateless example check
    print("Stateless LLM Response:")
    print(generate_response_stateless("What is the capital of France?", model_name="ollama/llama3:latest", sys_prompt="You are a helpful assistant."))

    #prompt = "What is the capital of France?"
    #response = llm.generate_response(prompt)
    #print(f"LLM Response: {response}")

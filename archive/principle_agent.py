import sys
import os
import openai

# Dummy context for demonstration
KNOWN_CONTEXT = {
    "hello": "Hi there! How can I assist you today?",
    "what is your name": "I am your principle agent."
}

def nlp2py(nl_query):
    """
    Dummy NLP-to-Python tool.
    For demonstration, only supports simple math expressions.
    """
    try:
        allowed = set("0123456789+-*/(). ")
        if all(c in allowed for c in nl_query.replace(" ", "")):
            result = eval(nl_query)
            return f"Result: {result}"
        else:
            return None  # Return None if not a math expression
    except Exception as e:
        return f"Error: {e}"

def openai_response(prompt):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "gpt-4" if you have access
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return completion.choices[0].message['content'].strip()
    except Exception as e:
        return f"OpenAI API error: {e}"

def principle_agent(user_input):
    normalized = user_input.strip().lower()
    for key in KNOWN_CONTEXT:
        if key in normalized:
            return KNOWN_CONTEXT[key]
    math_result = nlp2py(normalized)
    if math_result is not None:
        return math_result
    # Use OpenAI LLM for other queries
    return openai_response(user_input)

if __name__ == "__main__":
    print("Principle Agent (type 'exit' to quit)")
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            print("Goodbye!")
            sys.exit(0)
        response = principle_agent(user_input)
        print("Agent:", response)
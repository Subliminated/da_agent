import gradio as gr

def chat(user_message, history):
    print(f"User message: {user_message}")
    print(f"History: {history}")
    history = history or []
    agent_response = f"Agent: You said '{user_message}'"
    history.append((user_message, agent_response))  # Use tuple format
    return "", history

with gr.Blocks() as demo:
    gr.Markdown("# Simple Chatbot Conversation")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="Your message")
    msg.submit(chat, [msg, chatbot], [msg, chatbot])

if __name__ == "__main__":
    demo.launch(debug=True)
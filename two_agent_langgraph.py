from langgraph.graph import StateGraph
from typing import TypedDict, Union
from tools import agent_class
import json

STATES = ["intro", "collect_requirements", "forecast", "insights", "what_if", "end_conversation"]
min_required_keys = ["business_unit", "Job Family", "Growth Rate", "Automation Risk", "Attrition Rate"]

# Provide an explanation of the agent is required to do for each state
state_task_map = {
    "intro": "In this phase, you are requireed to give context to the user about the purpose of the agent and what it can do. You should also ask the user to provide their business unit, job family, and any paradigm shifts they are considering.",
    "collect_requirements": """
    
    You are to gather business context from the user relating to workforce planning, ask any clarifying questions as if you were an expert in strategic workforce planning. 
    The Goal is to at minimum capture any business units of interest, job families, and assumptions about growth, attrition and automation risks in the requirements field. Once you have captured this information, you should ask the user if they want to proceed to the next stage or if they want to add another assumption",
    In the Json object you must attempty to capture for the following keys: Business unit: str, Job Family: str, Growth Rate: float, Automation Risk: opt one of ["low","med","high"], Attrition Rate: float.
    For example: {"business_unit": "engineering", "Job Family": "software engineer", "Growth Rate": 0.05, "Automation Risk": "low", "Attrition Rate": 0.1}
    """,
    "forecast": "You are to send the forecast request to the Analyst Agent and wait for the results. If the user wants to run the forecast again, set the code_output to None.",
    "insights": "Generate insights based on the forecast results. Ask the user if they want to edit assumptions, explore what-if scenarios, run the forecast again, or end the conversation.",
    "end_conversation": "end the conversation and thank the user for their time. ensure you set the end_conversation flag to True in fields.",
}

# Valid tranisitions between states
STATE_GRAPH = {
    "intro": ["collect_requirements"],
    #"context": ["context","requirements"],
    "collect_requirements": ["collect_requirements", "forecast"],
    #"requirements": ["requirements","execution"],
    "forecast": ["insights"],
    "insights": ["requirements", "end_conversation"],
    #"what_if": ["execution", "end_conversation"],
    "end_conversation": []
}

# StateSchema is required to define the structure of the state used in the conversation
class StateSchema(TypedDict):
    user_message: Union[str, None]  # to capture user input
    conversation_stage: str
    #business_unit: Union[str, None]
    #job_family: Union[str, None]
    #paradigm_shift: Union[str, None]
    #model_choice: str
    requirements: dict
    forecast_results: Union[dict, None]
    code_request: Union[dict, None]
    code_output: Union[dict, None]
    end_conversation: bool
    exploration_type: Union[str, None]  # "edit_assumptions" or "what_if"
    assumption_overrides: dict  # temporary values for what-if
    
# --- Shared State Format ---
def initial_state():
    return {
        "user_message": None,  # to capture user input
        "conversation_stage": "intro", # THIS DRIVES THE STATE MACHINE
        # Stages: "intro", "context", "assumptions", "forecast", "insights", "end_conversation"
        #"business_unit": None,
        #"job_family": None,
        #"paradigm_shift": None,
        #"model_choice": "ollama/llama3:latest",
        "requirements": {"business_unit": "engineering", "Job Family": "software engineer", "Growth Rate": 0.05, "Automation Risk": "low", "Attrition Rate": 0.1},               # now a list of strings
        "forecast_results": None,
        "code_request": None,
        "code_output": None,
        "end_conversation": False,
        "exploration_type": None,         # "edit_assumptions" or "what_if"
        "assumption_overrides": {},       # temporary values for what-if
    }

SYSTEM_PROMPT = """You are a workforce planning assistant helping a business leader.
    Your job is to determine what the user is trying to do next and extract any useful parameters and response to user requests

    Your ultimate goal is to gather modelling requirements from the user, run a workforce planning forecast, and provide insights based on the results.

    Your task is to:
    1. Guide the user using helpful natural language messages by responding to their input.
    2. Extract any user inputs and store them in the state under the requirements field.
    3. Determine the user's intent's based on their inputs and progress the conversation through the stages defined in the state graph.

    For your informatio the state flow is as follows:
    States: intro → collect_requirements → forecast → insights → end_conversation
    You will be provided the current state and possible next states in conversation.

    You must ALWAYS return a JSON object with:
    {
    "next_stage": string (one of ["collect_requirements", "forecast", "insights", "end_conversation"]),
    "requirements": dict (must include keys "business_unit", "growth_rate", "automation_risk", "attrition_rate"),
    "response": string (a message relating to the current task)
    }
    """
Example = """
    Examples:
    User: I'm in the engineering business unit.
    → {
    "next_stage": "collect_requirements",
    "requirements": {"business_unit": "engineering", "Job Family": "software engineer", "Growth Rate": 0.05, "Automation Risk": "low", "Attrition Rate": 0.1},               # now a list of strings},
    "response": "Thanks, I've recorded that you're in the engineering business unit. Would you like to provide more context about your job family or any paradigm shifts you're considering?"
    }

    User: Try running the forecast again.
    → {
    "next_stage": "forecast,
    "requirements": {},
    "response": "Okay, running the forecast again now. Please wait a moment."
    }

    User: I’m done for now.
    → {
    "next_stage": "end_conversation",
    "requirements": {},
    "response": "Understood. Ending our session. Feel free to reach out to me anytime."
    }

    User: I would like to change my assumptions
    → {
    "next_stage": "collect_requirements",
    "requirements": {},
    "response": "Understood. Let's revisit your assumptions. Please provide the updated values."
    }
"""

# --- Agents --- 
'Create agent instance here as they are stateful and we want to reuse them with the context of the conversation'

first_response = "SME Agent: Welcome! I'm your Workforce Planning Assistant. My goal is to help you model what your workforce could look like in 2030. Would you like to begin?"
messages = [{"role": "system", "content": SYSTEM_PROMPT},
{"role": "assistant", "content": first_response}, 
]  # Initialize history with system prompt
principle_agent = agent_class.LiteLLM(model_name="ollama/llama3:latest", history=messages)  # This is the main agent that will handle the conversation
#analyst_agent = agent_class.LiteLLM(model_name="ollama/llama3:latest", system_prompt=SYSTEM_PROMPT) # Worry about this later

def agent_prompt_framework(state, additional_context = ""):

    #NOTE - we do not require user input, as this is captured in the state    
    # Contextualise the user input to provide a semi-stateful response

    valid_next_stages = STATE_GRAPH[state['conversation_stage']]
    prompt = f"""
        Based on the current state of the conversation ({state['conversation_stage']}), your current task is as follows: {state_task_map[state['conversation_stage']]}

        The current state data of the conversation is as follows:
        {json.dumps(state, indent=2)}
        
        Respond the user appropriately and provide guidance on next stage in JSON format.

        The next stage must be one of the following: {valid_next_stages}
    """ + "\n" + additional_context

    # Create Agent instance
    response = agent_class.generate_response_stateless(prompt,model_name="ollama/llama3:latest", sys_prompt=SYSTEM_PROMPT)
    count = 0
    while count<5:
        try:
            # Preprocess the response to ensure it's valid JSON
            response = response.strip()
            if not response.startswith("{") or not response.endswith("}"):
                #search for the first "{" and remove everything before it
                start_index = response.find("{")
                if start_index != -1:
                    response = response[start_index:]
                else:
                    print("Invalid response format:", response)
                    count += 1
                    continue
            
            # Also remove any trailing characters after the closing brace
            end_index = response.rfind("}")
            if end_index != -1:
                response = response[:end_index + 1]
            else:
                print("Invalid response format:", response)
                count += 1
                continue

            result = json.loads(response)
            if not all(k in result for k in ["next_stage", "requirements", "response"]):
                print("Missing keys in response:", response)
                count += 1
                continue
            
            #Check if the next_stage is valid, if not then rerun the agent for a response
            if result["next_stage"] not in STATES and result["next_stage"] not in valid_next_stages:
                print(f"Invalid next_stage '{result['next_stage']}' in response:", response)
                feedback_message = f"Invalid next_stage '{result['next_stage']}' provided. Please ensure it is one of {valid_next_stages}. and rerun\n\n"
                response = agent_class.generate_response_stateless(feedback_message+prompt,model_name="ollama/llama3:latest", sys_prompt=SYSTEM_PROMPT)
                count += 1
                continue

            return result
        
        except json.JSONDecodeError:
            print("Failed to parse response:", response)
            count += 1
            continue
    return {"next_stage": "", "requirements": {},"response":""}

# --- SME Agent ---

def sme_agent_node(state):
    current_stage = state["conversation_stage"]
    note = ''
    # Agent-driven prompts
    #if state["user_message"] is None: # Always process the user message

    #### PRE-WORK TO DETERMINE RESPONSE BASED ON STAGE ####
    if current_stage == "intro":
        #During the intro stage, we can provide a welcome message and ask the user to start the conversation"""   
        print(f"\n{first_response}")
    elif current_stage == "collect_requirements":
        #print("\nSME Agent: Let's gather your workforce context. What business unit are you from? What job families do you want to focus on? Any major paradigm shifts?")
        
        # In this stage, we want to add a prompt to tell the LLM to AVOID asking input from the user if we have already captured the data in the requirements field
        note = "Note: AVOID asking the user for input if the requirements field already contains the necessary information. Instead, provide a summary of the current requirements and ask if they want to edit them."

    elif current_stage == "insights":
        #print("\nSME Agent: Would you like to explore what-if scenarios or end the session?")
        pass
        note = ''

    ## Completely agent orchestrated state machine and conversation

    #Await for user input
    user_input = input("\nBusiness leader: ")
    state["user_message"] = user_input

    result = agent_prompt_framework(state, additional_context=note)

    print(f"\n\nRaw LLM result:\n{result}\n\n")
    next_stage = result.get("next_stage") #Extract the best logical next step based on the user response
    requirements = result.get("requirements", []) # Extract the fields or provided by the user if any
    response = result.get("response", "")  # Extract the response to the user by the LLM

    print(f"\nSME Agent: {response}")

    # POST RESONSE PROCESSING    
    # Update requirements in the state ONLY if they are gathered from the context or requirements stage
    if current_stage == "collect_requirements":
        # Set new requirements based on the LLM response
        #state["requirements"] = requirements
        if isinstance(requirements, dict):
            # Ensure requirements is a dictionary
            state["requirements"].update(requirements)
        elif isinstance(requirements, list):
            # If requirements is a list, convert it to a dictionary with empty values
            state["requirements"] = {req: "" for req in requirements}
        else:
            print(f"Unexpected requirements format: {requirements}. Expected dict or list.")

        ### Check if the requirements meet the minimum required keys, if not the next stage must still be collect_requirements
        if all(key in state["requirements"] and state["requirements"][key] for key in min_required_keys):
            # If all required keys are present, we can move to the next stage
            if next_stage == "collect_requirements":
                print("SME Agent: Great! I have captured your requirements. Would you like to proceed to the forecast stage?")
            elif next_stage == "forecast":
                print("SME Agent: Moving on to the forecast stage.")

    # Determine next stage
    next_stage = result.get("next_stage")
    if next_stage == "end_conversation":
        state["end_conversation"] = True
    else:
        state["conversation_stage"] = next_stage

    state["user_message"] = None
    return state

# --- Analyst Agent ---
def analyst_agent_node(state):
    request = state.get("code_request")
    if not request:
        return state

    params = request["params"]
    # Fake forecast logic
    result = {
        "new_roles": 12,
        "redundant_roles": 4,
        "modified_roles": 5,
        "note": f"Forecast for {params['unit']} / {params['job_family']} with paradigm {params['paradigm']}"
    }
    state["code_output"] = result
    return state

# --- Router Logic ---
def router(state):
    if state.get("end_conversation"):
        return "__end__"
    stage = state["conversation_stage"]
    if stage in ["forecast"] and not state.get("code_output"):
        return "analyst_agent"
    return "sme_agent"

# --- Build the Graph ---
def build_graph():
    builder = StateGraph(StateSchema)
    builder.add_node("sme_agent", sme_agent_node)
    builder.add_node("analyst_agent", analyst_agent_node)
    builder.set_entry_point("sme_agent")
    builder.add_conditional_edges("sme_agent", router)
    builder.add_conditional_edges("analyst_agent", router)
    return builder.compile()

# --- Main Execution ---
if __name__ == "__main__":
    graph = build_graph()
    state = initial_state()

    # Initial Test message 
    #print("SME Agent: I'm your Workforce Planning Assistant. What brings you here today? Which business unit or job family would you like to focus on?")
    for _ in range(50):  # max steps
        state = graph.invoke(state)
        if state["conversation_stage"] == "insights":
            break

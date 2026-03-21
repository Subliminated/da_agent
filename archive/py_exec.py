import csv
import traceback

# Simulated LLM function: converts NL to Python code string
def llm_generate_code(nl_instruction):
    # For demo, hardcoded mapping
    if "sum the values in column 'amount'" in nl_instruction.lower():
        return (
            "def process_csv(filename):\n"
            "    total = 0\n"
            "    with open(filename, newline='') as csvfile:\n"
            "        reader = csv.DictReader(csvfile)\n"
            "        for row in reader:\n"
            "            total += float(row['amount'])\n"
            "    return total\n"
        )
    else:
        return "# Unable to generate code for the given instruction."

# Executes generated code and captures errors
def execute_generated_code(code_str, csv_filename):
    local_vars = {}
    try:
        exec(code_str, {'csv': csv}, local_vars)
        result = local_vars['process_csv'](csv_filename)
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": traceback.format_exc()}

# Iterative improvement loop
def iterative_code_generation(nl_instruction, csv_filename, max_attempts=3):
    for attempt in range(max_attempts):
        print(f"Attempt {attempt+1}:")
        code_str = llm_generate_code(nl_instruction)
        print("Generated code:\n", code_str)
        outcome = execute_generated_code(code_str, csv_filename)
        if outcome["error"]:
            print("Error encountered:\n", outcome["error"])
            # In real scenario, error would be fed back to LLM for improvement
            nl_instruction += f" (Previous error: {outcome['error'].splitlines()[-1]})"
        else:
            print("Execution result:", outcome["result"])
            return outcome["result"]
    print("Failed after multiple attempts.")
    return None

# Example usage
if __name__ == "__main__":
    nl_instruction = "Sum the values in column 'amount' in the CSV file."
    csv_filename = "example.csv"  # Ensure this file exists with an 'amount' column
    iterative_code_generation(nl_instruction, csv_filename)
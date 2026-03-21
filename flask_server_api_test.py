# Test script to run the Flask app and check its functionality
import requests
def test_flask_app():
    # URL of the Flask app
    url = "http://localhost:8888/"

    # Send a GET request to the root endpoint
    response = requests.get(url)

    # Check if the response is successful
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    # Check if the response text is as expected
    assert response.text == "Code Runner API is up!", f"Unexpected response text: {response.text}"

    print("Flask app is running and responding correctly.")

# Create function to pass through python code string to the Flask app
# This code string is a simple example that computes the average of flower lengths from a CSV file
# The CSV file is expected to be mounted at /data/flowers.csv in the Docker container
code_string = """
import pandas as pd

# Load the CSV from shared volume
df = pd.read_csv("/data/example.csv")

# Option 1: Compute average of 'sepal_length' and 'petal_length' separately
avg_sepal = df["sepal_length"].mean()
avg_petal = df["petal_length"].mean()

print(f"Average Sepal Length: {avg_sepal}")
print(f"Average Petal Length: {avg_petal}")

# Option 2: Compute overall average of all flower length values combined
overall_avg = df[["sepal_length", "petal_length"]].values.mean()
print(f"Overall Average Flower Length: {overall_avg}")
"""

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
        print(output_str)
        return output_str
    else:
        output_str = f"[ERROR] {response.status_code}: {response.text}"
        print(output_str)
        return output_str

if __name__ == "__main__":
    test_flask_app()
    code_executor(code_string)
    print("Test completed successfully.")
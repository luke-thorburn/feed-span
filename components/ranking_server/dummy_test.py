import requests
import test_data


# URL of the server
url = "http://0.0.0.0:8001/rank"  # Replace with the actual URL of the server

# Send POST request to the server
response = requests.post(url, json=test_data.BASIC_EXAMPLE)

# Print the response
if response.status_code == 200:
    print("Response:")
    print(response.json())
else:
    print("Failed to receive response. Status code:", response.status_code)

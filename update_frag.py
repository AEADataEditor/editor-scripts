import requests

# Set up the API endpoint and the data for the PATCH request
api_endpoint = "https://api.bitbucket.org/2.0/repositories/{account_name}/{repo_slug}/issues/{issue_id}"
data = {"status": "B"}

# Set up the headers for the request
headers = {
    "Authorization": "Bearer {access_token}",
    "Content-Type": "application/json"
}

# Send the PATCH request to update the issue
response = requests.patch(api_endpoint, json=data, headers=headers)

# Check the status code of the response to see if the request was successful
if response.status_code == 200:
    print("Issue updated successfully")
else:
    print("Error updating issue: {}".format(response.status_code))


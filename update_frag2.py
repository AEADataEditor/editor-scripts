import requests

# Set up the API endpoint and the data for the PATCH request
api_endpoint = "https://api.bitbucket.org/2.0/repositories/{account_name}/{repo_slug}/issues/{issue_id}"
data = {"status": "B"}

# Set up the headers for the request
headers = {
    "Authorization": "Bearer {access_token}",
    "Content-Type": "application/json"
}

# Send a GET request to retrieve the issue
response = requests.get(api_endpoint, headers=headers)

# Check the status code of the response to see if the request was successful
if response.status_code == 200:
    # Parse the response data to get the current status of the issue
    issue_data = response.json()
    current_status = issue_data["status"]

    # Check if the current status is "Pre-approved" or "Report under review"
    if current_status == "Pre-approved" or current_status == "Report under review":
        # Send the PATCH request to update the issue
        response = requests.patch(api_endpoint, json=data, headers=headers)

        # Check the status code of the response to see if the request was successful
        if response.status_code == 200:
            print("Issue updated successfully")
        else:
            print("Error updating issue: {}".format(response.status_code))
    else:
        print("Issue cannot be moved to status B")
else:
    print("Error retrieving issue: {}".format(response.status_code))


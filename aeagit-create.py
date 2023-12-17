#!/usr/bin/env python3
import os
import argparse
from dotenv import load_dotenv  
import requests
from requests.exceptions import ConnectionError

# defaults
workspace = "aeaverification"  
import_repo_url = "https://github.com/AEADataEditor/replication-template.git"

# Get home directory 
home_dir = os.path.expanduser("~") 

# Construct full .env file path
env_file = os.path.join(home_dir, ".envvars")



def initialize_repo(consumer_user, consumer_key, workspace, project_key, repo_slug, import_repo_url):

    print(f"Importing repository {repo_slug} to workspace {workspace}...")
    
    # OAuth authentication 
    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)

    # Construct API URL
    api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}'
    
    # Repository import data
    data = {
        "scm": "git",
        "project": {"key": project_key}, 
        "forkable": "true",
        "import_url": import_repo_url
    }
    
    # Make API call
    try:
        response = requests.post(api_url, auth=auth, json=data)
        response.raise_for_status()
        
    except ConnectionError:
        print(f"Error: Could not connect to Bitbucket to import {repo_url}")
        
    if response.status_code in (200,201):
        print(f"Successfully created repository {repo_slug} to {workspace}")  
        print(f"URL: {response.json()['links']['html']['href']}") 
        #import_repo_code(auth, workspace, repo_slug, import_repo_url)
    else:
        print(f"Failed to import repository: {response.status_code}, {response.reason}")

# Import code into repository

def import_repo_code(auth, workspace, repo_slug, import_repo_url):

    repo_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests"
    
    data={
            "source": {
                "branch": {
                    "name": "master"
                }, 
                "repository": {
                   "full_name": import_repo_url
                }
            },
            "destination": {
                "branch": {
                   "name": "master"
                }
            }
        }
    
    try:
        response = requests.post(repo_url, auth=auth, json=data)
        response.raise_for_status()
        
    except ConnectionError:
        print(f"Error: Could not connect to Bitbucket to import {repo_url}")
        
    except requests.exceptions.HTTPError as err:
        if response.status_code == 404:
            print(f"Error: Repository {repo_slug} not found") 
        else:
            print(f"Bitbucket error ({err.response.status_code}): {err.response.reason}")
            
    except Exception as err:
        print(f"An error occurred importing into {repo_slug}")
        print(f"Error: {err}")
        
    else: 
        print(f"Successfully imported code into {repo_slug} on Bitbucket")

def main():
    parser = argparse.ArgumentParser(description='Initialize AEA Bitbucket repository')
    parser.add_argument('-r','--repo_slug', required=True, help='Repository name (should be the first Jira issue)')
    parser.add_argument('-p','--project', required=False, default="AER", help='Journal project key (default: AER)')
    args = parser.parse_args()
    
    # Load environment variables  
    load_dotenv(env_file)
    consumer_user= os.getenv('P_BITBUCKET_USER')
    consumer_key = os.getenv('P_BITBUCKET_PAT')


    
    initialize_repo(consumer_user, consumer_key, workspace, 
                args.project, args.repo_slug, import_repo_url)

if __name__ == "__main__":
    main()
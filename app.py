from flask import Flask, render_template, request, redirect, url_for, flash
import google.generativeai as genai
from PyPDF2 import PdfReader
import os
import json
from dotenv import load_dotenv
import requests

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
app = Flask(__name__)
app.secret_key = 'supersecretkey'
load_dotenv()  # Load all our environment variables
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_gemini_response(input):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(input)
    return response.text

def input_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def fetch_github_profile(username, proxies=None):
    user_url = f"https://api.github.com/users/{username}"
    response = requests.get(user_url, proxies=proxies)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch GitHub profile")

def fetch_github_repositories(username, proxies=None):
    repos_url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(repos_url, proxies=proxies)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch repositories")

def fetch_repo_languages(repo_full_name, proxies=None):
    languages_url = f"https://api.github.com/repos/{repo_full_name}/languages"
    response = requests.get(languages_url, proxies=proxies)
    if response.status_code == 200:
        return response.json()
    else:
        return {}

def analyze_repository(repo, proxies=None):
    analysis = {
        'files': [],
        'readme': False,
        'commit_count': 0,
        'languages': []
    }
    contents_url = repo['contents_url'].replace('{+path}', '')
    response = requests.get(contents_url, proxies=proxies)
    content = response.json() if response.status_code == 200 else []

    for file in content:
        analysis['files'].append(file['name'])

    readme_url = f"https://api.github.com/repos/{repo['full_name']}/readme"
    response = requests.get(readme_url, proxies=proxies)
    if response.status_code == 200:
        analysis['readme'] = True

    commits_url = repo['commits_url'].replace('{/sha}', '')
    response = requests.get(commits_url, proxies=proxies)
    commits = response.json() if response.status_code == 200 else []
    analysis['commit_count'] = len(commits)

    languages = fetch_repo_languages(repo['full_name'], proxies)
    analysis['languages'] = list(languages.keys())

    return analysis

def fetch_pull_requests(repo_full_name, proxies=None):
    pulls_url = f"https://api.github.com/repos/{repo_full_name}/pulls"
    response = requests.get(pulls_url, proxies=proxies)
    return response.json() if response.status_code == 200 else []

def fetch_issues(repo_full_name, proxies=None):
    issues_url = f"https://api.github.com/repos/{repo_full_name}/issues"
    response = requests.get(issues_url, proxies=proxies)
    return response.json() if response.status_code == 200 else []

def verify_contributions(username, repos, proxies=None):
    contributions = {}
    for repo in repos:
        pulls = fetch_pull_requests(repo['full_name'], proxies)
        issues = fetch_issues(repo['full_name'], proxies)

        contributions[repo['full_name']] = {
            'pull_requests': [pr for pr in pulls if pr['user']['login'] == username],
            'issues': [issue for issue in issues if issue['user']['login'] == username]
        }
    return contributions

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        uploaded_file = request.files['resume']
        github_username = request.form['username']
 
        if uploaded_file and github_username:
            text = input_pdf_text(uploaded_file)
            
            proxy = {
                'http': 'http://sqkkntta:d14mt7uod40p@38.154.227.167:5868/',
                'https': 'http://sqkkntta:d14mt7uod40p@38.154.227.167:5868/'
            }

            try:
                user = fetch_github_profile(github_username, proxies=proxy)
                repos = fetch_github_repositories(github_username, proxies=proxy)
                contributions = verify_contributions(github_username, repos, proxies=proxy)
                
                repo_analysis = []
                for repo in repos:
                    analysis = analyze_repository(repo, proxies=proxy)
                    repo_analysis.append({
                        'full_name': repo['full_name'],
                        'files': analysis['files'],
                        'readme': analysis['readme'],
                        'commit_count': analysis['commit_count'],
                        'languages': analysis['languages']
                    })

                result = {
                    'user': user,
                    'repos': repo_analysis,
                    'contributions': contributions,
                    'filename': uploaded_file.filename
                }

                result_json = json.dumps(result, indent=4)
                input_prompt = f"""
                Hey Act Like a Mechanism which compare a resume and Github data with a deep understanding of tech field, software engineering, data science, data analyst and big data engineer. Your task is to evaluate the resume based on the given Github data. You must consider the job market is very competitive.Assign the percentage of skills validated based on Github data and resume skill with high accuracy

resume: {text}

Github data :{result_json}

I want the response in one single string having the structure ,also give me the summary of the Validation ,Unmatched skills 
{{"total percentage of Skills validated ":"%", "Matched Skills":[], "Unmatched Skills":[], "Profile Summary":"",  }}

                """

                response = get_gemini_response(input_prompt)
                return render_template('result.html', response=response)
            
            except Exception as e:
                return f"An error occurred: {e}"

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)

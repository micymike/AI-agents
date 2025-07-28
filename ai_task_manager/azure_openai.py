import requests
from config import AZURE_OPENAI_API_KEY

# Use the user-supplied endpoint for chat completions
AZURE_OPENAI_CHAT_ENDPOINT = "https://kidus-mafuwv4a-eastus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"

def ask_openai(prompt, max_tokens=128, temperature=0.5):
    url = AZURE_OPENAI_CHAT_ENDPOINT
    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    # Extract the assistant's reply from the chat/completions API
    if "choices" in result and result["choices"]:
        return result["choices"][0]["message"]["content"].strip()
    return ""

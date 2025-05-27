import json
import requests
import yaml

# 静态参数
models = {
    "granite":{
        "url": "https://granite-3-2-8b-instruct--apicast-production.apps.int.stc.ai.prod.us-east-1.aws.paas.redhat.com:443/v1/chat/completions",
        "token": "",
        "model": "ibm-granite/granite-3.2-8b-instruct"
    },
    "mistral":{
        "url": "https://mistral-7b-instruct-v0-3--apicast-production.apps.int.stc.ai.prod.us-east-1.aws.paas.redhat.com/v1/chat/completions",
        "token": "",
        "model": "mistralai/Mistral-7B-Instruct-v0.3"
    }
}
temperature = 0.7

messages = []


def get_model(modelName):
    """
    GET LLM model by the model name
    All available models can be found in models
    
    Params:
        modelName: the model name string
    Return:
        An model object, for example:
        {
            "url": "",
            "token": "",
            "model": ""
        }
    """
    return models.get(modelName, None)

def ask_me(question, modelName):
    """
    Ask the AI a question
    
    Params:
        question: the question or prompt
        modelName: the model name string
    return:
        returns nothing but will update messages object.
    """
    
    model = get_model(modelName)

    token = model.get("token")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # the first question must come from a user
    message = {
        "role" : "user",
        "content" : question
    }
    messages.append(message)
    
    print("User question is: ", question[:100])

    data = {
        "model": model.get("model"),
        "messages": messages,
        "temperature": temperature,
        "chat_template_kwargs": { 
            "thinking": True 
        }
    }

    # Send user question
    url = model.get("url")
    x = requests.post(url=url, headers=headers, json=data)

    if x.status_code != 200:
        raise Exception("Request AI api failed, status code is: ", x.status_code)

    # Get response from AI
    res = json.loads(x.text)
    choices = res.get("choices", [])
    
    if not choices:
        print("There are issues, the response is:")
        print(x.text)
        return
    
    res_role = choices[0]["message"]["role"]
    res_content = choices[0]["message"]["content"]
    message = {
        "role" : res_role,
        "content" : res_content
    }
    
    # Update massage list
    messages.append(message)

    
if __name__ == '__main__':
    model = "mistral"
    question = "I am an experienced programmer and I am familar with yaml files"
    ask_me(question=question, modelName=model)
    
    question = "Please sort the tests elements in below yaml file and give me the full file"
    ask_me(question=question, modelName=model)
    
    e2e_yaml = "ci-operator/config/openshift/openshift-tests-private/openshift-openshift-tests-private-release-4.19__multi-nightly-4.19-upgrade-from-stable-4.19.yaml"
    with open(e2e_yaml, 'r') as file:
        content = file.read()
        ask_me(question=content, modelName=model)
        
    print(messages[-1].get("content"))
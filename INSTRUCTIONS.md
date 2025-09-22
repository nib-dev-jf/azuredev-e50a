# VS Code for the Web - Azure AI Foundry

We've generated a simple development environment for you to play with sample code to create and run the agent that you built in the Azure AI Foundry playground.

The Azure AI Foundry extension provides tools to help you build, test, and deploy AI models and AI Applications directly from VS Code. It offers simplified operations for interacting with your models, agents, and threads without leaving your development environment. Click on the Azure AI Foundry Icon on the left to see more.

Follow the instructions below to get started!

## Open the terminal

Press ``Ctrl-` `` &nbsp; to open a terminal window.

## Run your model locally

To run the model that you deployed in AI Foundry and view the output in the terminal:

```bash
python run_model.py
```


## Run the Streamlit UI

Place a `.env` file in the repo root (same folder as this file) with at least:

```
ENDPOINT_URL=<your-azure-openai-endpoint>
DEPLOYMENT_NAME=<your-model-deployment>
AZURE_OPENAI_API_KEY=<your-key>
```

Then:

```bash
pip install -r requirements-dev.txt
streamlit run ./streamlit_app/app.py
```

The app will still load even if env vars are missing (chatting will be disabled until configured).

## Run the backend API (FastAPI)

```bash
pip install -r src/requirements.txt
uvicorn src.api.main:create_app --factory --reload --port 8000
```

## Run the React frontend (dev server)

```bash
cd src/frontend
pnpm install
pnpm dev
```

The dev server proxies /chat and /static to http://localhost:8000.

## Deploy with azd

Initialize and deploy:

```bash
azd init -t https://github.com/Azure-Samples/get-started-with-ai-chat
azd up
```

Tear down:

```bash
azd down
```



## Continuing on your local desktop

You can keep working locally on VS Code Desktop by clicking "Continue On Desktop..." at the bottom left of this screen. Be sure to take the .env file with you using these steps:

- Right-click the .env file
- Select "Download"
- Move the file from your Downloads folder to the local git repo directory
- For Windows, you will need to rename the file back to .env using right-click "Rename..."

import os
import httpx



# # Load env variables from a file (local purposes only)
# with open("./.env") as f:
#     for line in f.readlines():
#         k, v = line.strip().split("=", 1)
#         os.environ[k] = v.strip("'")


# Bring in deps including Slack Bolt framework
from slack_bolt import App
from flask import Flask, request, jsonify
from slack_bolt.adapter.flask import SlackRequestHandler


# Set variables for calling team
TEAM_SERVER_BASE_URL = os.getenv("TEAM_SERVER_BASE_URL")
TEAM_SERVER_API_KEY = os.getenv("TEAM_SERVER_API_KEY")
TEAM_ID = os.getenv("TEAM_ID")


def query_host_assistant(query: str, metadata: dict={}):
    """
    Sends a query to the host assistant server and returns the response.

    Args:
        query (str): The query to send to the host assistant.
        metadata (dict, optional): Additional metadata to include with the query. Defaults to {}.

    Returns:
        dict: The response from the host assistant server.

    Raises:
        Exception: If there is an error while sending the query.

    """
    if TEAM_ID is None:
        return {"error": "TEAM_ID is not set."}
    if TEAM_SERVER_BASE_URL is None:
        return {"error": "TEAM_SERVER_BASE_URL is not set."}
    if TEAM_SERVER_API_KEY is None:
        return {"error": "TEAM_SERVER_API_KEY is not set."}
    
    inputs = {"query": query}
    response = httpx.post(
        f"{TEAM_SERVER_BASE_URL}/v1/teams/run",
        headers={"x-api-key": TEAM_SERVER_API_KEY},
        json={"team_id": TEAM_ID, "inputs": inputs, "metadata": metadata},
        timeout=60,
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# Initialize Bolt app with token and secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
handler = SlackRequestHandler(app)

# start flask app
flask_app = Flask(__name__)

# join the #bot-testing channel so we can listen to messages
channel_list = app.client.conversations_list().data
channel = next((channel for channel in channel_list.get('channels') if channel.get("name") == "bot-testing"), None)
channel_id = channel.get('id')
app.client.conversations_join(channel=channel_id)
print(f"Found the channel {channel_id} and joined it")

# get the bot's own user ID so it can tell when somebody is mentioning it
auth_response = app.client.auth_test()
bot_user_id = auth_response["user_id"]

# this is the challenge route required by Slack
# if it's not the challenge it's something for Bolt to handle
@flask_app.route("/", methods=["POST"])
def slack_challenge():
    if request.json and "challenge" in request.json:
        print("Received challenge")
        return jsonify({"challenge": request.json["challenge"]})
    else:
        print("Incoming event:")
        print(request.json)
    return handler.handle(request)




@app.message()
def reply(message, say):
    # the slack message object is a complicated nested object
    # if message contains a "blocks" key
    #   then look for a "block" with the type "rich text"
    #       if you find it 
    #       then look inside that block for an "elements" key
    #           if you find it 
    #               then examine each one of those for an "elements" key
    #               if you find it
    #                   then look inside each "element" for one with type "user"
    #                   if you find it  
    #                   and if that user matches the bot_user_id 
    #                       then it's a message for the bot
    if message.get('blocks'):
        for block in message.get('blocks'):
            if block.get('type') == 'rich_text':
                for rich_text_section in block.get('elements'):
                    for element in rich_text_section.get('elements'):
                        if element.get('type') == 'user' and element.get('user_id') == bot_user_id:
                            for element in rich_text_section.get('elements'):
                                if element.get('type') == 'text':
                                    query = element.get('text')

                                    # # Context of the conversation.

                                    # replies = app.client.conversations_replies(
                                    #     channel=message.get('channel'),
                                    #     ts=message.get('thread_ts')
                                    # )

                                    # for r in replies['messages']:
                                    #     pass

                                    if message.get('thread_ts') is None:   # Message not in a thread
                                        threadID = message.get('ts')
                                    else:
                                        threadID = message.get('thread_ts')

                                    metadata = {'slack_thread_id': threadID}
                                    response = query_host_assistant(query , metadata)

                                    if "response" in response:
                                        response_text = response["response"]
                                    elif "error" in response:
                                        response_text = response["error"]
                                    else:
                                        response_text = "An unknown error occurred. Check the logs for more information."

                                    app.client.chat_postMessage(
                                        channel=message.get('channel'),
                                        thread_ts=message.get('ts'), 
                                        text=response_text
                                    )
                                    return
                                


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=os.getenv("PORT", 8080))

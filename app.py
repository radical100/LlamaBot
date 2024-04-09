# read .env files
import dotenv, os
dotenv.load_dotenv()

# Bring in deps including Slack Bolt framework
from slack_bolt import App
from flask import Flask, request, jsonify
from slack_bolt.adapter.flask import SlackRequestHandler

# bring in llamaindex deps and initialize index
from llama_index import VectorStoreIndex, Document

index = VectorStoreIndex([])

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

# this handles any incoming message the bot can hear
# we want it to only respond when somebody messages it directly
# otherwise it listens and stores every message as future context



from llama_index import VectorStoreIndex, ServiceContext
from llama_index.retrievers import VectorIndexRetriever
from llama_index.embeddings import HuggingFaceEmbedding, OpenAIEmbedding
from llama_index.llms import OpenAI




llm = OpenAI("gpt-3.5-turbo-0125")

embed_model = OpenAIEmbedding(model = 'text-embedding-3-small')

service_context = ServiceContext.from_defaults(
    llm=llm,
    embed_model=embed_model,
)


import chromadb
from chromadb.config import Settings


chroma_client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./assets/vectorestores/chroma" # Optional, defaults to .chromadb/ in the current directory
))

collection_name = "host_index"
chroma_collection = chroma_client.get_collection(collection_name)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)




index = VectorStoreIndex.from_vector_store(
    vector_store, service_context=service_context
)


from llama_index.response_synthesizers import get_response_synthesizer
from llama_index.prompts import SelectorPromptTemplate, PromptTemplate, PromptType
from llama_index.prompts.utils import is_chat_model
from llama_index.core.llms.types import ChatMessage, MessageRole
from llama_index.prompts.base import ChatPromptTemplate


TEXT_QA_PROMPT = PromptTemplate(
    template=(
        "Context information is below.\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n"
        "Given the context information and not prior knowledge, "
        "answer the query.\n"
        "Query: {query_str}\n"
        "Answer: "
    ),
    prompt_type=PromptType.QUESTION_ANSWER,
)
TEXT_QA_PROMPT_TMPL_MSGS = [
    ChatMessage(
        content=(
            "You are a QA assistant that provides reccomendations, examples and "
            "instructions on how to use the codebase.\n"
            "Always answer the query using the provided context information, "
            "and not prior knowledge.\n"
            "Some rules to follow:\n"
            "1. Always include reference to a source of the information."
            "Include numbered reference in square brackets in the answer text "
            "and list of used references by 'file_path' in the end.\n"
            "2. If asked for a code example, always include it in a code block ```python ... ```."
        ),
        role=MessageRole.SYSTEM,
    ),
    ChatMessage(
        content=(
            "Context information is below.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Given the context information and not prior knowledge, "
            "answer the query.\n"
            "Query: {query_str}\n"
            "Answer: "
        ),
        role=MessageRole.USER,
    ),
]
CHAT_TEXT_QA_PROMPT = ChatPromptTemplate(message_templates=TEXT_QA_PROMPT_TMPL_MSGS)


text_qa_template = SelectorPromptTemplate(
    default_template=TEXT_QA_PROMPT,
    conditionals=[(is_chat_model, CHAT_TEXT_QA_PROMPT)],
)


response_synthesizer = get_response_synthesizer(
    service_context=service_context,
    text_qa_template=text_qa_template,
)


query_engine = index.as_query_engine(response_synthesizer=response_synthesizer)




import IPython.display as ipd




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

                                    response = query_engine.query(query)
                                    say(response.response)
                                    return
                                

if __name__ == "__main__":
    flask_app.run(port=3000)

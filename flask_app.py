from flask import Flask, render_template, request, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_, desc
from openai import OpenAI
import yaml
import random
import os

app = Flask(__name__)
app.config["DEBUG"] = True

# -----------------------------------------------------------------------------
# --- CONSTANTS
# -----------------------------------------------------------------------------
patientdata_filename = "/home/chrispebble/hmgpt/patient-beta.yaml"
gpt_model = "gpt-3.5-turbo"
our_temp = 1.0


for rule in app.url_map.iter_rules():
    print(rule)

# -----------------------------------------------------------------------------
# --- Function definitions
# -----------------------------------------------------------------------------

def get_client():
    """
    Create and return an OpenAI client instance.
    """
    client = OpenAI(api_key=os.getenv("HMGPT_API_KEY"), organization=os.getenv("HMGPT_ORG"))
    return client

def get_patient(patients_filename=patientdata_filename):
    """
    Reads patient data from a YAML file then selects a patient based on weighted probabilities.

    Returns:
    dict: The selected patient dictionary.

    Note:
    - The function assumes that the YAML file is properly formatted and each patient's data
      is separated into different documents within the file.
    """
    patients = {}
    with open(patients_filename, "r") as file:
        patients = list(yaml.safe_load_all(file))
    prob_wts = [p['prob_wt'] for p in patients]
    pt = random.choices(range(len(patients)), weights=prob_wts, k=1)
    return patients[pt[0]]

def get_this_patient(patient_id, patients_filename=patientdata_filename):
    """
    Reads patient data from a YAML file and returns patient with specific patient_id

    Returns:
    dict: The selected patient dictionary, if found,

    Note:
    - The function assumes that the YAML file is properly formatted and each patient's data
      is separated into different documents within the file.
    """
    patients = {}
    with open(patients_filename, "r") as file:
        patients = list(yaml.safe_load_all(file))
    for p in patients:
        print(type(p['id']))
        print(type(patient_id))
        if int(p['id']) is int(patient_id):
            return p
    return None

def compile_hx_next(pt, chatlog, next_line):
    talk_hx = [{"role": "system", "content": pt['framing']}]
    for line in chatlog:
        if line.line_type == "user":
            talk_hx = talk_hx + [{"role": "user", "content": line.line_content }]
        elif line.line_type == "assistant":
            talk_hx = talk_hx + [{"role": "assistant", "content": line.line_content }]
        # other line_types are ignored
    talk_hx = talk_hx + [{"role": "user", "content": next_line }]
    talk_hx = talk_hx + [{"role": "user", "content": pt['reminders']}]
    return talk_hx

def get_transcript(chatlog):
    """
    Generate a transcript from a conversation history.

    Returns:
    str: A formatted transcript of the conversation.
    """
    transcript = ""
    for line in chatlog:
        if line.line_type == "user":
            transcript += "<p><b>Student</b>: " + line.line_content + "</p>"
        elif line.line_type == "assistant":
            transcript += "<p style='color:grey;'><b>Patient</b>: " + line.line_content + "</p>"

    return transcript


# --- Connect to MySQL database-------------------------------------------------
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="chrispebble",
    password=os.getenv("MYSQL_PASSWORD"),
    hostname="chrispebble.mysql.pythonanywhere-services.com",
    databasename="chrispebble$hmgpt",
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --- Create SQLAlchemy Model --------------------------------------------------
class ChatLog(db.Model):

    __tablename__ = "chatlog"

    key = db.Column(db.Integer, primary_key=True)    # unique number for every item in table
    session_id = db.Column(db.Integer)               # unique session number for every interaction
    user_id = db.Column(db.String(254))              # user id (e-mail)
    line_type = db.Column(db.String(100))
    line_content = db.Column(db.String(4096))
    patient_id = db.Column(db.Integer)
    stage = db.Column(db.String(10))


# --- GET, POST methods --------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "GET":
        # add code here to collect the user email
        return render_template("index.html")

    if request.form["action"] == "Start":
        # get the session id, patient_id
        user_email = request.form["user_email"]
        user_email = user_email.strip();
        return render_template("main_page.html",
                               user_email=user_email)


# --- CASE START PAGE --------------------------------------------------------
@app.get("/case/<int:case_id>")
def case_get(case_id):

    # --- NEW CONVERSATION ---

    # get the next session id by adding  one to the last (max) session id
    max_sid = db.session.query(func.max(ChatLog.session_id)).scalar()
    # curr_sid = max_sid + 1

    # If the database is empty and max_sid is None, start with session_id 1
    if max_sid is None:
        curr_sid = 1
    else:
        curr_sid = max_sid + 1

    # Load the patient case indicated by case_id
    pt = get_this_patient(case_id)

    # Show the main page
    return render_template("case_page.html",
                            session_id=curr_sid,
                            patient_id=pt['id'],
                            case_id=case_id,
                            patient_intro=pt['intro'],
                            chatlog=[])
                            # user_email is passed in the url query string
                            # pre/post is passed in the url query string


# --- CASE CONTINUE PAGE --------------------------------------------------------
@app.post("/case_continue") #, methods=["POST"])
def show_case_continue():

    # Get OpenAI Client
    client = get_client()

    # --- RECEIVED INPUT FOR CONVERSATION ---

    if request.form["action"] == "Send":

        # get the session id, patient_id
        curr_sid = request.form["session_id"]
        patient_id = request.form["patient_id"]
        user_email = request.form["user_email"]
        case_id = request.form["case_id"]
        stage = request.form["stage"]

        # get the patient associated with this id
        pt = get_this_patient(patient_id)

        # get the current conversation so far
        chatlog = ChatLog.query.filter_by(session_id=curr_sid).all()

        # get the user input
        next_line = request.form["user_input"]

        # add the new line of conversation to database
        new_entry = ChatLog(user_id=user_email,
                            session_id=curr_sid,
                            patient_id=int(patient_id),
                            stage=stage,
                            line_type="user",
                            line_content=next_line)
        db.session.add(new_entry)

        # compile entire conversation into a talk_hx
        talk_hx = compile_hx_next(pt, chatlog, next_line)

        # send the entire conversation to openai to get the next response
        response = client.chat.completions.create(model=gpt_model, messages=talk_hx, temperature=our_temp)

        # extract the reply (only the 0th element actually exists)
        reply = response.choices[0].message.content

        # add the ChatGPT reply to database
        new_entry = ChatLog(user_id=user_email,
                            session_id=curr_sid,
                            patient_id=int(patient_id),
                            stage=stage,
                            line_type="assistant",
                            line_content=reply)
        db.session.add(new_entry)

        # now commit all DB changes
        db.session.commit()

        # only display user's messages and chatgpt replies
        chats = ChatLog.query.filter_by(
                                session_id=curr_sid).filter(
                                    or_(ChatLog.line_type == "user",
                                        ChatLog.line_type == "assistant")).all()

        # render the new page
        return render_template("case_continue.html",
                                session_id=curr_sid,
                                user_email=user_email,
                                patient_id=patient_id,
                                case_id=case_id,
                                stage=stage,
                                patient_intro=pt['intro'],
                                chatlog=chats)



# --- REVIEW PREVIOUS SESSIONS -------------------------------------------------
@app.get("/review") #, methods=["GET"])
def review_sessions():

    # only display user's messages and chatgpt replies
    sessions = (ChatLog.query
                         .with_entities(ChatLog.session_id, ChatLog.user_id, ChatLog.stage, ChatLog.patient_id)
                         .filter(ChatLog.line_type == "user")
                         .distinct()
                         .order_by(desc(ChatLog.session_id))
                         .all())

    return render_template("review_sessions.html", sessions=sessions)


@app.get("/review/<int:session_id>") #, methods=["GET"])
def view_session(session_id):
    # get the current conversation
    chatlog = ChatLog.query.filter_by(session_id=session_id).all()
    transcript = get_transcript(chatlog)
    return render_template("view_session.html",
                           transcript=transcript,
                           session_id=session_id,
                           user_id=chatlog[0].user_id,
                           stage=chatlog[0].stage,
                           patient_id=chatlog[0].patient_id)


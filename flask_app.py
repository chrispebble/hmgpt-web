from flask import Flask, render_template, request, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
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
        if p['id'] == patient_id:
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
            transcript += "Student: " + line.line_content + "\n\n"
        elif line.line_type == "assistant":
            transcript += "Patient: " + line.line_content + "\n\n"

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


# --- GET, POST methods --------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    # Get OpenAI Client
    client = get_client()

    # --- NEW CONVERSATION ---

    if request.method == "GET":
        max_sid = db.session.query(func.max(ChatLog.session_id)).scalar()
        curr_sid = max_sid + 1

        # Randomly choose a patient from the default file
        pt = get_patient()
        # add the patient framing to the database
        new_entry = ChatLog(session_id=curr_sid, line_type="framing", line_content=pt['framing'])
        db.session.add(new_entry)

        # add the patient framing to the database
        new_entry = ChatLog(session_id=curr_sid, line_type="reminders", line_content=pt['reminders'])
        db.session.add(new_entry)

        db.session.commit()

        return render_template("main_page.html",
                                session_id=curr_sid,
                                patient_id=pt['id'],
                                patient_intro=pt['intro'],
                                chatlog=[])

    # REDIRECT REQUESTS TO CREATE NEW CONVERSATION to "/"
    if request.form["action"] == "New Conversation":
        return redirect(url_for('index'))


    # --- RECEIVED INPUT FOR CONVERSATION ---
    if request.form["action"] == "Send":

        # get the session id, patient_id
        curr_sid = request.form["session_id"]
        patient_id = request.form["patient_id"]

        # get the patient associated with this id
        pt = get_this_patient(patient_id)

        # get the current conversation so far
        chatlog = ChatLog.query.filter_by(session_id=curr_sid).all()

        # get the user input
        next_line = request.form["user_input"]

        # add the new line of conversation to database
        new_entry = ChatLog(session_id=curr_sid, line_type="user", line_content=next_line)
        db.session.add(new_entry)

        # compile entire conversation into a talk_hx
        talk_hx = compile_hx_next(pt, chatlog, next_line)

        # send the entire conversation to openai to get the next response
        response = client.chat.completions.create(model=gpt_model, messages=talk_hx, temperature=our_temp)
        # get the reply (only the 0th element actually exists)
        reply = response.choices[0].message.content

        # add the ChatGPT reply to database
        new_entry = ChatLog(session_id=curr_sid, line_type="assistant", line_content=reply)
        db.session.add(new_entry)

        # now commit all changes
        db.session.commit()

        # only display user's messages and chatgpt replies
        chats = ChatLog.query.filter_by(
                                session_id=curr_sid).filter(
                                    or_(ChatLog.line_type == "user",
                                        ChatLog.line_type == "assistant")).all()

        # render the new page
        return render_template("main_page.html",
                                session_id=curr_sid,
                                patient_id=patient_id,
                                patient_intro=pt['intro'],
                                chatlog=chats)

    # --- STUDENT DONE WITH CONVERSATION ---
    if request.form["action"] == "Grade":

        # Get OpenAI Client
        client = get_client()

        # get the session id, patient_id
        curr_sid = request.form["session_id"]
        patient_id = request.form["patient_id"]
        # get the patient associated with this id
        pt = get_this_patient(patient_id)

        # -----------------------------------------------------------------------------
        # --- Summarize the interaction
        # -----------------------------------------------------------------------------

        # get the current conversation so far
        chatlog = ChatLog.query.filter_by(session_id=curr_sid).all()
        # compile entire conversation into a talk_hx
        transcript = get_transcript(chatlog)

        # create request to summarize the transcript
        sum_statement = "Summarize this interaction between a student and patient."

        # add summary-statement to database
        new_entry = ChatLog(session_id=curr_sid, line_type="summary-statement", line_content=sum_statement )
        db.session.add(new_entry)

        # format for request
        sum_statement = [{"role": "system", "content": sum_statement}]

        # turn transcript into gpt format
        transcript = [{"role": "user", "content": transcript }]

        # create query
        query = sum_statement + transcript

        # send the entire conversation to openai to get the next response
        response = client.chat.completions.create(model=gpt_model, messages=query, temperature=our_temp)
        # get the reply (only the 0th element actually exists)
        gpt_summary = response.choices[0].message.content

        # add the ChatGPT reply to database
        new_entry = ChatLog(session_id=curr_sid, line_type="summary", line_content=gpt_summary)
        db.session.add(new_entry)

        # turn it into gpt format
        gpt_summary = [{"role": "assistant", "content": gpt_summary}]

        # -----------------------------------------------------------------------------
        # --- Compare the interaction to the goal interaction
        # -----------------------------------------------------------------------------

        eval_goal = pt['goal'] + "\nHow did the student do at meeting these goals?"

        # add expectation statement to database
        new_entry = ChatLog(session_id=curr_sid, line_type="expectation", line_content=pt['goal'] )
        db.session.add(new_entry)

        # turn it into a request
        eval_goal = [{"role": "user", "content": eval_goal}]

        # create the query
        eval_statement = [{"role": "system", "content": "You are an instructor, evaluating an interaction between a student and a patient."}]
        query = eval_statement + transcript + gpt_summary + eval_goal

        # ask chatGPT
        response = client.chat.completions.create(model=gpt_model,
                                                    messages=query,
                                                    temperature=our_temp)
        evaluation = response.choices[0].message.content

        # add comparison to database
        new_entry = ChatLog(session_id=curr_sid, line_type="evaluation", line_content=evaluation)
        db.session.add(new_entry)

        # turn it into gpt format
        evaluation = [{"role": "assistant", "content": evaluation}]

        # -----------------------------------------------------------------------------
        # --- How could the student improve next time
        # -----------------------------------------------------------------------------

        final_question = pt['goal'] + "\nDid the student meet every one of these goals?  Just say 'Yes' or 'No'."

        # add question to database
        new_entry = ChatLog(session_id=curr_sid, line_type="final-question", line_content=final_question)
        db.session.add(new_entry)

        # format response for next query
        final_question = [{"role": "user", "content": final_question}]

        # create the query
        query = eval_statement + transcript + gpt_summary + final_question

        # ask chatGPT
        response = client.chat.completions.create(model=gpt_model,
                                                    messages=query,
                                                    temperature=our_temp)
        final = response.choices[0].message.content

        # add final response
        new_entry = ChatLog(session_id=curr_sid, line_type="final", line_content=final)
        db.session.add(new_entry)

        # commit all changes
        db.session.commit()

        # pull back the curtain and show the entire conversation
        everything = ChatLog.query.filter_by(session_id=curr_sid).all()

        # now redirect to the summary page
        return render_template("summary_page.html",
                                session_id=curr_sid,
                                patient_id=patient_id,
                                patient_intro=pt['intro'],
                                biglog=everything)



    # --- RECEIVED INPUT FOR FEEDBACK ---
    if request.form["action"] == "Submit Feedback":

        # get the session id, patient_id, response
        curr_sid = request.form["session_id"]
        patient_id = request.form["patient_id"]
        response = request.form["user_input"]

        # store the feedback in the database
        new_entry = ChatLog(session_id=curr_sid, line_type="feedback", line_content=response)
        db.session.add(new_entry)
        db.session.commit()

        # render the final page
        return render_template("done.html")


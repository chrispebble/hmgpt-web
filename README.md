# HMGPT Web
Web version of the HMGPT project.

## Try it out
* [HM GPT](https://hmgpt-chrispebble.pythonanywhere.com/) (password required)

Currently there are only two cases: a simple uncomplicated URI, and a URI in a patient with type 2 diabetes.

## Create Cases
Cases can be created by modifying the `patient-beta.yaml` file.  Below is an example case, with comments explaining each variable.

```yaml
---
id: uri-basic
#   id is character string (no spaces) that should be unique to each case

prob_wt: 1
#   The weighting that should be given to this case for the random selection
#   process.  The probability that a case is chosen is it's weight, divided
#   by the total of all weights.  For example, if there are three cases and each
#   has a prob_wt of 1, then each case has a 33.3% chance of being picked.  But
#   if two cases are both weighted 1, and the last is weighted 8, then that last
#   one has an 80% chance of being picked, and the other two each have a 10% chance.

intro: This is an adult female.
#   This line is displayed to the student when they start a new case.

framing: Act as a patient who has a common cold.  I want you to only reply as the patient.
    When I ask questions, only answer the immediate question.
    Do not give extra information. Do not write explanations.
    Answer the questions and wait for my response.
    Your vital signs are temperature 100.4 fahrenheit, heart rate 88, respiratory rate 14, pulse oximetry 96%.
    You take birth control and have not had sex since your last period.
    You have seasonal allergies.
#   Framing is fed to chatGPT as a 'system' message.  It should set the stage for
#   the patient encounter, and include any relevent information required for the student
#   to correctly interact with the patient.

reminders: Remember to act as a patient with a common cold but do not tell me you have a common cold.
#   Because chatGPT can sometimes forget, the "reminders" are fed in with each interaction
#   to keep the AI on track.  If you notice the AI has a tendency to forget something you can add
#   it to the reminders.

goal: This patient had a common cold.
    The patient should have been given instructions on how to take care of these symptoms at home.
    The patient should be told to return if they are not improving or if symptoms worsen.
#   This is how the student will be evaluated at the end of the interaction.
#   You should tell the AI what the student was expected to do.
```

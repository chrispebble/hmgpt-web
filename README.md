# HMGPT Web
Web version of the HMGPT project.

## Try it out
* [HM GPT](https://hmgpt-chrispebble.pythonanywhere.com/) (password required)
* [HM GPT Review](https://hmgpt-chrispebble.pythonanywhere.com/review) (password required)

Currently there are only two cases: a simple uncomplicated URI, and a URI in a patient with type 2 diabetes.

Interact with the patient as you would a normal patient.  When you think you are done with the scenario, hit __Grade__ to be evaluated!  If you want to skip the scenario, hit __New Conversation__.

The number and case id are displayed currently - that is just for debugging purposes.

### Things to try
Start out basic:
* How can I help you today?
* What are your symptoms today?
* How long have you had these symptoms?
* What are your vitals?

Maybe some ROS type questions:
* Have you ever had these symptoms before?
* Do you have any shortness of breath?
* Have you been having trouble swallowing?

Get into medical history:
* Do you have any medical conditions?
* Do you take any medications?
* Is it possible you are pregnant?
* Do you have any allergies?
* Do you have any allergies to medications?
* Have you ever experienced these symptoms before?

Tell the patient what you think
* Your symptoms are consistent with a common cold.
* You should stay home and rest, drink plenty of fluids.
* You can take over the counter medications such as Tylenol for your symptoms.

Finish it up
* You do not need to see a medical provider today, but if your symptoms do not improve in 2-3 days then you should come back.
* You need to see a medical provider today.
* Do you have any questions?

## Case Descriptions:
1.  Adult Cold, uncomplicated
2.  Adult Cold, VS outside of range and chills and body aches
3.  Sore Throat, uncomplicated
4.  Sore Throat, CENTOR+ should be tested
5.  Pediatric Cold, uncomplicated
6.  Pediatric Cold, with headache and HR 112
7.  UTI, uncomplicated
8.  UTI, complicated
9.  Pregnancy test request, uncomplicated
10. Pregnancy test request, concern for spotting/pain/VS
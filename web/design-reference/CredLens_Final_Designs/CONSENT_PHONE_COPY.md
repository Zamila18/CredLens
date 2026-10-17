# CredLens phone consent — exact bilingual copy and states

Use with `CLAUDE_CODE_INSTRUCTIONS.md`. All phone interactions are local demo state: no consent API mutation or persistent consent record. Bangla is primary and English secondary. The prescribed Bengali digits in this copy may be normalized to English digits in the implementation to follow the product-wide Latin-digit rule; preserve meaning and keep English digits consistent.

## Desktop wrapper

- Title: Mock consent page
- Description: What a merchant would see on their phone before any data is used. A demo screen only: nothing here is sent to the API and no consent is recorded.
- Link: ← Back to Consent
- Every phone: Demo screen · not live / Synthetic demo data
- Review note outside phone: The Bangla on this screen needs a native-speaker review before the demo.

## Consent page 1 — Ask

**আপনার তথ্য ব্যবহারের অনুমতি**  
Permission to use your data

ঋণের প্রস্তুতি যাচাই করতে আমরা নিচের তথ্য দেখব।  
To check readiness for credit, we will look at the information below.

Required, checked and locked:

- মাল কেনার হিসাব  
  Stock purchases · Mokam
- ডেলিভারির হিসাব  
  Deliveries and returns · REDX
- পেমেন্টের হিসাব  
  Repayments · Baki

Optional, checked by default and toggleable:

আর্থিক অভ্যাসের ১০টি প্রশ্ন (ঐচ্ছিক)  
10 financial-habit questions · optional, never part of the score

প্রশ্নগুলো দেখুন  
See the 10 questions

কেন: শুধু ঋণের প্রস্তুতি যাচাই  
Why: Only to check readiness for credit

কতদিন: ২ বছর  
How long: 2 years

বাতিল: যেকোনো সময় অনুমতি তুলে নিতে পারবেন  
Withdraw: You can withdraw at any time

**সিদ্ধান্ত নেবেন একজন কর্মকর্তা, কম্পিউটার নয়।**  
A credit officer decides, not a computer.

Primary: অনুমতি দিন / Give permission  
Secondary: এখন না / Not now

## Consent page 2 — Questions opened

**আর্থিক অভ্যাসের ১০টি প্রশ্ন**  
The 10 financial-habit questions

উত্তর পরে একজন কর্মকর্তা আপনার সাথে কথা বলে নেবেন। এগুলো স্কোরের অংশ নয়।  
An officer will ask you these later. They are not part of the score.

Read-only here: no answer buttons. This preview is different from the officer's editable questionnaire.

### খরচ — Spend

1. গত এক মাসে দোকানের আয় খরচের চেয়ে বেশি ছিল।  
   Over the last month, the shop's money coming in was more than its spending.
2. দোকান সরবরাহকারীর টাকা ও বিল সময়মতো পরিশোধ করে।  
   The shop pays its suppliers and bills on time.

### সঞ্চয় — Save

3. একটি খারাপ মাস সামলানোর মতো টাকা দোকানের জমা আছে।  
   The shop has money set aside that could cover a bad month.
4. মালিক নিয়মিত কিছু টাকা জমান।  
   The owner puts money aside regularly.

### ধার — Borrow

5. দোকানের এখনকার ঋণ সামলানো যায় বলে মনে হয়।  
   The shop's current debts feel manageable.
6. দোকান যে বাকি বা ঋণ নেয়, তার খরচ কত তা মালিক জানেন।  
   The owner knows what the credit the shop uses costs.

### পরিকল্পনা — Plan

7. মালিক দোকানের টাকাপয়সা নিয়ে আগে থেকে পরিকল্পনা করেন।  
   The owner plans ahead for the shop's money.
8. বিক্রি কমে গেলে দোকানের একটি বিকল্প পরিকল্পনা আছে।  
   The shop has a backup plan if sales drop.

### প্রেক্ষাপট — Context

9. দোকানের টাকাপয়সা নিয়ে দুশ্চিন্তা মালিককে কতটা চাপে রাখে?  
   How much stress do money worries about the shop cause the owner?
10. আগামী এক বছরে দোকানের আর্থিক অবস্থা নিয়ে মালিক আত্মবিশ্বাসী।  
    The owner feels confident about the shop's finances for the coming year.

প্রতিটি উত্তর ১ থেকে ৫-এর মধ্যে।  
Each answer is from 1 to 5.

Button: ফিরে যান / Go back

## Consent page 3 — Consent given

Large calm check mark.

**অনুমতি দেওয়া হয়েছে**  
Permission given

তারিখসহ অনুমতি রাখা হয়েছে। এখন একজন কর্মকর্তা আপনার দোকান পর্যালোচনা করবেন।  
Consent recorded with the date. A credit officer will now review your shop.

Default optional-scope-checked summary:

কেনা, ডেলিভারি, পেমেন্ট এবং প্রশ্নের উত্তর।  
Purchases, deliveries, payments and the questionnaire answers.

When optional scope was unchecked, use truthful summary instead:

কেনা, ডেলিভারি এবং পেমেন্টের হিসাব।  
Purchases, deliveries and payments.

Outlined button: অনুমতি তুলে নিন / Withdraw consent

Helper: Withdraw consent: your data stops being used for scoring

The desktop demo notice remains visible: this success copy is simulated, not an actual database-write confirmation.

## Consent page 4 — Not now

**ঠিক আছে, অনুমতি দেওয়া হয়নি**  
All right, no permission given

অনুমতি ছাড়া আপনার দোকানের কোনো স্কোর তৈরি হবে না। পরে চাইলে আবার দেখতে পারেন।  
Without permission, no score is made for your shop. You can look again later.

Button: আবার দেখুন / Look again

## Consent page 5 — Consent withdrawn

**অনুমতি তুলে নেওয়া হয়েছে**  
Consent withdrawn

আপনার তথ্য আর স্কোরের জন্য ব্যবহার হবে না।  
Your data is no longer used for scoring.

Button: আবার দেখুন / Look again

Use a calm neutral shield/minus or similar symbol, not a red error/prohibition symbol.

## Officer questionnaire (separate interaction on merchant detail)

The same ten questions become editable only for officers with valid consent including the questionnaire scope. Each answer is an integer1–5. Labels: Not at all true → Completely true, with No stress → A lot of stress for question9. Show `7 of 10 answered` dynamically, not as a fixed label. Cancel leaves stored answers unchanged. Save answers is disabled until all10 are answered. Saving replaces previous answers; the readiness score does not change. Keep `Directional · not part of the score` visible. Use the existing API's category aggregation; do not silently invent reverse-coding or a composite score.

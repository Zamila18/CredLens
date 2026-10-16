# QUESTIONNAIRE.md: the ten financial-habit questions

Source of truth for the wording. The dashboard's copy is `web/src/pages/merchant/questionnaireItems.ts` and must match this page. Status (Oct 16): English drafted by Dipto and checked by the lead; **Bangla drafted, waiting for a native-speaker review** before the demo.

How the answers are used: each answer is 1 to 5. The four subscores (spend, save, borrow, plan) are the mean of their two items; stress and confidence are shown on their own. The answers are shown **beside** the score as a directional signal and are never a model input (PROJECT_BRIEF section 18; the ablation measures them separately as run D). Saving answers never changes the score.

Where the wording comes from: the four indicators of the FinHealth Score (spend, save, borrow, plan; FinHealth Score Toolkit, linked in `docs/DATA_SOURCES.md`), adapted to a shop. The items are our own wording, not copied from the toolkit.

| Key | Group | English | Bangla (draft) | 1 means | 5 means |
|---|---|---|---|---|---|
| spend1 | Spend | Over the last month, the shop's money coming in was more than its spending. | গত এক মাসে দোকানের আয় খরচের চেয়ে বেশি ছিল। | Not at all true / একদম সত্য নয় | Completely true / পুরোপুরি সত্য |
| spend2 | Spend | The shop pays its suppliers and bills on time. | দোকান সরবরাহকারীর টাকা ও বিল সময়মতো পরিশোধ করে। | as above | as above |
| save1 | Save | The shop has money set aside that could cover a bad month. | একটি খারাপ মাস সামলানোর মতো টাকা দোকানের জমা আছে। | as above | as above |
| save2 | Save | The owner puts money aside regularly. | মালিক নিয়মিত কিছু টাকা জমান। | as above | as above |
| borrow1 | Borrow | The shop's current debts feel manageable. | দোকানের এখনকার ঋণ সামলানো যায় বলে মনে হয়। | as above | as above |
| borrow2 | Borrow | The owner knows what the credit the shop uses costs. | দোকান যে বাকি বা ঋণ নেয়, তার খরচ কত তা মালিক জানেন। | as above | as above |
| plan1 | Plan | The owner plans ahead for the shop's money. | মালিক দোকানের টাকাপয়সা নিয়ে আগে থেকে পরিকল্পনা করেন। | as above | as above |
| plan2 | Plan | The shop has a backup plan if sales drop. | বিক্রি কমে গেলে দোকানের একটি বিকল্প পরিকল্পনা আছে। | as above | as above |
| stress | Context | How much stress do money worries about the shop cause the owner? | দোকানের টাকাপয়সা নিয়ে দুশ্চিন্তা মালিককে কতটা চাপে রাখে? | No stress / কোনো চাপ নেই | A lot of stress / অনেক চাপ |
| confidence | Context | The owner feels confident about the shop's finances for the coming year. | আগামী এক বছরে দোকানের আর্থিক অবস্থা নিয়ে মালিক আত্মবিশ্বাসী। | Not at all true / একদম সত্য নয় | Completely true / পুরোপুরি সত্য |

Direction: for every item a higher number is the healthier answer, except **stress**, where 5 means a lot of stress (the generator, `src/synth/generate.py`, reverse-codes it the same way).

For the native-speaker review: check that each sentence sounds natural to a shop owner in Bangladesh, that "বাকি" (shop credit) is the right word in borrow2, and that nothing sounds like an accusation. Write corrections in this table and in the dashboard file together.

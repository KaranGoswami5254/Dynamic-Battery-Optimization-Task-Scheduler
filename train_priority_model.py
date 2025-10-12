# train_priority_model.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pickle
from sklearn.metrics import classification_report

df = pd.read_csv("priority_data_full.csv")


X = df[["energy", "deadline_hours", "cpu", "battery"]]
y = df["priority"].map({"Low": 0, "Medium": 1, "High": 2})  

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


clf_priority = RandomForestClassifier(n_estimators=200, random_state=42)
clf_priority.fit(X_train, y_train)

y_pred = clf_priority.predict(X_test)
print("\n--- Classification Report on Test Set ---")
print(classification_report(y_test, y_pred))

with open("priority_model.pkl", "wb") as f:
    pickle.dump(clf_priority, f)

print("✅ Priority model trained and saved as priority_model.pkl")

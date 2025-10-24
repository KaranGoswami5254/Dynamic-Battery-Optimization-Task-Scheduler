import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import pickle

df = pd.read_csv("priority_data_full.csv")

df["priority"] = df["priority"].map({"Low": 0, "Medium": 1, "High": 2})

# Feature engineering
df["energy_per_cpu"] = df["energy"] / df["cpu"].replace(0, 1)
df["cpu_battery_ratio"] = df["cpu"] / df["battery"].replace(0, 1)
df["deadline_inverse"] = 1 / df["deadline_hours"].replace(0, 1)

X = df[["energy", "deadline_hours", "cpu", "battery",
         "energy_per_cpu", "cpu_battery_ratio", "deadline_inverse"]]
y = df["priority"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

clf_priority = RandomForestClassifier(
    n_estimators=300,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=3,
    class_weight='balanced_subsample',
    random_state=42
)
clf_priority.fit(X_train, y_train)

y_pred = clf_priority.predict(X_test)

print("\n--- Classification Report ---")
print(classification_report(y_test, y_pred))

with open("priority_model.pkl", "wb") as f:
    pickle.dump(clf_priority, f)

print("✅ Balanced and improved priority model saved as priority_model.pkl")

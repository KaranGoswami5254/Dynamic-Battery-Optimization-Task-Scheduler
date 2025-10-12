import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import pickle
import os

csv_file = "tasks_large.csv"  

if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
    print(f"✅ Loaded dataset from {csv_file}")
else:
    raise FileNotFoundError(f"{csv_file} not found in the current folder.")


required_columns = ["battery", "cpu", "temp", "priority", "decision"]
if not all(col in df.columns for col in required_columns):
    raise ValueError(f"CSV must contain columns: {required_columns}")


X = df[["battery", "cpu", "temp", "priority"]]
y = df["decision"].map({"Run": 1, "Pause": 0})  


X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

# ----------------------
# 6. Evaluate
# ----------------------
y_pred = clf.predict(X_test)
print("\n--- Classification Report on Test Set ---")
print(classification_report(y_test, y_pred))


with open("scheduler_model.pkl", "wb") as f:
    pickle.dump(clf, f)

print("\n✅ Model saved as scheduler_model.pkl")

from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

BASE_DIR = Path(__file__).resolve().parent
DATASET = BASE_DIR / "career_dataset.csv"
MODEL_DIR = BASE_DIR.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

data = pd.read_csv(DATASET)
X = data["resume_text"].fillna("")
y = data["career"].fillna("")
vectorizer = TfidfVectorizer()
X_vectorized = vectorizer.fit_transform(X)
model = LogisticRegression(max_iter=1000)
model.fit(X_vectorized, y)
joblib.dump(model, MODEL_DIR / "career_model.pkl")
joblib.dump(vectorizer, MODEL_DIR / "tfidf_vectorizer.pkl")
print("Model and vectorizer saved to", MODEL_DIR)

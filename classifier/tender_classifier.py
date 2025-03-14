import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import spacy
import logging
from typing import List, Dict, Tuple
import joblib
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TenderClassifier:
    def __init__(self):
        # Load spaCy's English model for NER
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Download if not available
            os.system("python -m spacy download en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")
        
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words='english'
        )
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42
        )
        self.category_mapping = {}
        self.is_trained = False

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for classification"""
        doc = self.nlp(text.lower())
        # Remove stopwords and punctuation
        tokens = [token.text for token in doc if not token.is_stop and not token.is_punct]
        return " ".join(tokens)

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text using spaCy"""
        doc = self.nlp(text)
        entities = {
            'organizations': [],
            'locations': [],
            'money': [],
            'dates': []
        }
        
        for ent in doc.ents:
            if ent.label_ == 'ORG':
                entities['organizations'].append(ent.text)
            elif ent.label_ == 'GPE' or ent.label_ == 'LOC':
                entities['locations'].append(ent.text)
            elif ent.label_ == 'MONEY':
                entities['money'].append(ent.text)
            elif ent.label_ == 'DATE':
                entities['dates'].append(ent.text)
        
        return entities

    def prepare_features(self, tenders: List[Dict]) -> Tuple[np.ndarray, List[str]]:
        """Prepare features for classification"""
        texts = []
        for tender in tenders:
            # Combine relevant fields for classification
            text = f"{tender.get('title', '')} {tender.get('description', '')}"
            texts.append(self.preprocess_text(text))
        
        # Transform texts to TF-IDF features
        X = self.vectorizer.fit_transform(texts)
        return X.toarray()

    def train(self, training_data: pd.DataFrame):
        """Train the classifier using historical tender data"""
        logger.info("Starting classifier training...")
        
        # Prepare features and labels
        X = self.prepare_features(training_data.to_dict('records'))
        
        # Create category mapping if not exists
        if not self.category_mapping:
            unique_categories = training_data['category'].unique()
            self.category_mapping = {cat: idx for idx, cat in enumerate(unique_categories)}
        
        y = training_data['category'].map(self.category_mapping)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train classifier
        self.classifier.fit(X_train, y_train)
        
        # Evaluate
        train_score = self.classifier.score(X_train, y_train)
        test_score = self.classifier.score(X_test, y_test)
        
        logger.info(f"Training score: {train_score:.3f}")
        logger.info(f"Test score: {test_score:.3f}")
        
        self.is_trained = True

    def classify_tender(self, tender: Dict) -> Dict:
        """Classify a single tender and extract relevant information"""
        if not self.is_trained:
            raise ValueError("Classifier must be trained before prediction")
        
        # Prepare text for classification
        text = f"{tender.get('title', '')} {tender.get('description', '')}"
        processed_text = self.preprocess_text(text)
        
        # Transform text to features
        X = self.vectorizer.transform([processed_text]).toarray()
        
        # Predict category
        category_idx = self.classifier.predict(X)[0]
        category = {v: k for k, v in self.category_mapping.items()}[category_idx]
        
        # Extract entities
        entities = self.extract_entities(text)
        
        # Calculate confidence score
        confidence_scores = self.classifier.predict_proba(X)[0]
        confidence = confidence_scores.max()
        
        return {
            'tender_id': tender.get('id'),
            'category': category,
            'confidence': float(confidence),
            'entities': entities,
            'risk_level': self._assess_risk(confidence, entities),
            'estimated_value': self._estimate_value(entities.get('money', []))
        }

    def _assess_risk(self, confidence: float, entities: Dict) -> str:
        """Assess risk level based on confidence and entities"""
        if confidence < 0.5:
            return 'high'
        elif confidence < 0.8:
            return 'medium'
        return 'low'

    def _estimate_value(self, money_entities: List[str]) -> Optional[float]:
        """Estimate tender value from money entities"""
        if not money_entities:
            return None
        
        # Extract numerical values from money entities
        values = []
        for money in money_entities:
            try:
                # Remove currency symbols and convert to float
                value = float(''.join(filter(str.isdigit, money)))
                values.append(value)
            except ValueError:
                continue
        
        return max(values) if values else None

    def save_model(self, path: str):
        """Save trained model and vectorizer"""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_data = {
            'classifier': self.classifier,
            'vectorizer': self.vectorizer,
            'category_mapping': self.category_mapping
        }
        joblib.dump(model_data, path)
        logger.info(f"Model saved to {path}")

    def load_model(self, path: str):
        """Load trained model and vectorizer"""
        model_data = joblib.load(path)
        self.classifier = model_data['classifier']
        self.vectorizer = model_data['vectorizer']
        self.category_mapping = model_data['category_mapping']
        self.is_trained = True
        logger.info(f"Model loaded from {path}")

def main():
    # Example usage
    classifier = TenderClassifier()
    
    # Load training data (you would need to provide this)
    try:
        training_data = pd.read_csv('training_data.csv')
        classifier.train(training_data)
        
        # Save the trained model
        classifier.save_model('tender_classifier_model.joblib')
        
        logger.info("Classifier training completed and model saved")
    except Exception as e:
        logger.error(f"Error during training: {str(e)}")

if __name__ == "__main__":
    main()

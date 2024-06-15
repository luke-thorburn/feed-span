import torch
import time
import pandas as pd
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers import DistilBertModel, DistilBertTokenizer, DistilBertForSequenceClassification

# Check if GPU is available and move the model to the appropriate device
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

#model_name = "kornosk/polibertweet-mlm"  # Replace with the specific PoliBERT model if needed
civic_tokenizer = AutoTokenizer.from_pretrained("./fine_tuned_polibert_unfreeze_1")
civic_model = AutoModelForSequenceClassification.from_pretrained("./fine_tuned_polibert_unfreeze_1")
civic_model.to(device)

# Load pre-trained BERT model and tokenizer
#model_name = 'distilbert-base-uncased'
bridge_tokenizer = DistilBertTokenizer.from_pretrained("./v4")
bridge_model = DistilBertForSequenceClassification.from_pretrained("./v4") 
bridge_model.to(device)


def getBridgeScore(text):

    # Tokenize the input text
    inputs = bridge_tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    input_ids = inputs['input_ids'].to(device)
    attention_mask = inputs['attention_mask'].to(device)
    
    # Perform inference
    bridge_model.eval()
    with torch.no_grad():
        outputs = bridge_model(input_ids, attention_mask=attention_mask)
        prediction = outputs.logits.item()
    
    return prediction


def areCivic(texts):
    # Tokenize the list of texts
    inputs = civic_tokenizer(texts, return_tensors="pt", truncation=True, padding=True)

    # Perform the classification
    with torch.no_grad():
        outputs = civic_model(**inputs)
        logits = outputs.logits

    # Convert logits to probabilities
    probs = torch.nn.functional.softmax(logits, dim=-1)

    # Get the predicted labels
    predicted_labels = torch.argmax(probs, dim=1).tolist()

    # Return list of booleans indicating if each text is "civic"
    return [label == 1 for label in predicted_labels]


def isCivic(text):
    inputs = civic_tokenizer(tweet, return_tensors="pt", truncation=True, padding=True)

    # Perform the classification
    with torch.no_grad():
        outputs = civic_model(**inputs)
        logits = outputs.logits

    # Convert logits to probabilities
    probs = torch.nn.functional.softmax(logits, dim=-1)

    # Get the predicted label
    predicted_label = torch.argmax(probs, dim=1).item()

    if predicted_label == 1:
        return True
    else:
        return False




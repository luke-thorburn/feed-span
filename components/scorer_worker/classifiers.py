import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers import DistilBertModel, DistilBertTokenizer, DistilBertForSequenceClassification
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

#print("Current working directory:", os.getcwd())


# Check if GPU is available and move the model to the appropriate device
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

civic_tokenizer = AutoTokenizer.from_pretrained("scorer_worker/model_civic")
civic_model = AutoModelForSequenceClassification.from_pretrained("scorer_worker/model_civic")
civic_model.to(device)

# # Load pre-trained BERT model and tokenizer
# bridge_tokenizer = DistilBertTokenizer.from_pretrained("scorer_worker/model_bridging")
# bridge_model = DistilBertForSequenceClassification.from_pretrained("scorer_worker/model_bridging") 
# bridge_model.to(device)

def areCivic(texts):

    # Tokenize the list of texts
    inputs = civic_tokenizer(texts, return_tensors="pt", truncation=True, padding=True).to(device)

    # Perform the classification
    with torch.no_grad():
        outputs = civic_model(**inputs)
        logits = outputs.logits

    # Convert logits to probabilities
    probs = torch.nn.functional.softmax(logits, dim=-1)

    # Get the predicted labels
    predicted_labels = torch.argmax(probs, dim=1).tolist()
    print(predicted_labels)

    # Return list of booleans indicating if each text is "civic"
    return [label == 1 for label in predicted_labels]

# def getBridgeScore(text):

#     # Tokenize the input text
#     logger.info(f'===== running on {device}')
#     inputs = bridge_tokenizer(text, return_tensors='pt', padding=True, truncation=True).to(device)
#     logger.info(f'===== tokenized')
#     input_ids = inputs['input_ids'].to(device)
#     attention_mask = inputs['attention_mask'].to(device)
    
#     # Perform inference
#     bridge_model.eval()
#     with torch.no_grad():
#         outputs = bridge_model(input_ids, attention_mask=attention_mask)
#         prediction = outputs.logits.item()
#     logger.info(f'===== predicted !!!')
    
#     return prediction


def isCivic(text):

    logger.info(f"USING DEVICE: {device}")

    inputs = civic_tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(device)
    logger.info(f'===== tokenized')
    # Perform the classification
    civic_model.eval()
    with torch.no_grad():
        outputs = civic_model(**inputs)
        logits = outputs.logits
    
    probs = torch.nn.functional.softmax(logits, dim=-1)

    predicted_label = torch.argmax(probs, dim=1).item()

    if predicted_label == 1:
        return True
    else:
        return False
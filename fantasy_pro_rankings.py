import requests
import json
import re
import pandas as pd

url = "https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php"
response = requests.get(url)
ecr_match = re.search(r'var ecrData = ({.*?});', response.text)
ecr_data = json.loads(ecr_match.group(1))
adp_match = re.search(r'var adpData = (\[.*?\]);', response.text)
adp_data = json.loads(adp_match.group(1))

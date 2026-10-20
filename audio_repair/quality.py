"""Conservative literal transcript checks; no fuzzy matches can turn bad words into successes."""
import re,unicodedata

def canon(text):
 text=''.join(c for c in unicodedata.normalize('NFKD',text) if unicodedata.category(c)!='Mn')
 text=text.translate(str.maketrans('أإآىة٠١٢٣٤٥٦٧٨٩','ااايه0123456789'));text=re.sub(r'[^\w\s]',' ',text)
 patterns={1964:r'الف\s+و?تسع(?:ميه|مايه|مائه|ماءه)\s+و?اربع[هه]?\s+و?ستين',1968:r'الف\s+و?تسع(?:ميه|مايه|مائه|ماءه)\s+و?(?:تمانيه|ثمانيه)\s+و?ستين',65:r'خمس[هه]?\s+و?ستين',200:r'\b(?:ميتين|متين|مايتين|ماتين)\b'}
 for value,pattern in patterns.items():text=re.sub(pattern,str(value),text)
 return text.split()
def speech_accuracy(expected,actual):
 a=canon(expected);b=canon(actual);row=list(range(len(b)+1))
 for i,left in enumerate(a,1):
  new=[i]
  for j,right in enumerate(b,1):new.append(min(new[-1]+1,row[j]+1,row[j-1]+(left!=right)))
  row=new
 return {'word_error_rate':row[-1]/max(1,len(a)),'word_edits':row[-1],'expected_tokens':a,'recognized_tokens':b,'ending_word_matches':bool(a and b and a[-1]==b[-1]),'fuzzy_spelling_acceptance':False}

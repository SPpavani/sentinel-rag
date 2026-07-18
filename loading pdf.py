
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("annual_report_2024.pdf")
pages = loader.load()
# Each page = one Document with metadata: {"source": "...", "page": 0}
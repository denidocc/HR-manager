import spacy

def analyze_text(text, lang):
    print(f"\n=== Анализ текста на {lang} ===")
    print(f"Текст: {text}")
    
    # Загружаем соответствующую модель
    model = "ru_core_news_lg" if lang == "русском" else "en_core_web_lg"
    nlp = spacy.load(model)
    
    # Обрабатываем текст
    doc = nlp(text)
    
    # Выводим результаты
    print("\nТокены и их части речи:")
    for token in doc:
        print(f"{token.text} - {token.pos_}")
    
    print("\nИменованные сущности:")
    for ent in doc.ents:
        print(f"{ent.text} - {ent.label_}")

# Тестовые тексты
russian_text = "Привет! Я программист Python с опытом работы 5 лет."
english_text = "Hello! I am a Python developer with 5 years of experience."

# Анализируем оба текста
analyze_text(russian_text, "русском")
analyze_text(english_text, "английском") 
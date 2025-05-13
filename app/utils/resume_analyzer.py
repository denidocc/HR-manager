#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flask import current_app
import spacy
import fitz  # PyMuPDF
import pytesseract
from PIL import Image as PILImage
from docx import Document as DocxDocument
import time
import re
from typing import Dict, List, Optional, Union
from app import db
import docx

class ResumeAnalyzer:
    """
    Класс для анализа резюме с использованием spaCy.
    Извлекает структурированные данные из резюме в различных форматах,
    включая отсканированные PDF-документы.
    """
    
    def __init__(self):
        """
        Инициализирует анализатор резюме.
        Загружает языковые модели для русского и английского языков.
        Загружает ключевые слова из базы данных.
        """
        try:
            # Загружаем языковые модели
            self.nlp_ru = spacy.load("ru_core_news_lg")
            self.nlp_en = spacy.load("en_core_web_lg")
            
            # Настраиваем Tesseract
            self.tesseract = pytesseract
            
            # Загружаем ключевые слова из базы данных
            self._load_keywords()
            
            current_app.logger.info("ResumeAnalyzer успешно инициализирован")
        except Exception as e:
            current_app.logger.error(f"Ошибка при инициализации ResumeAnalyzer: {str(e)}", exc_info=True)
            raise
    
    def _load_keywords(self):
        """Загрузка ключевых слов из базы данных"""
        from app.models import KeywordCategory, Keyword
        
        self.keywords = {}
        
        # Получаем все категории
        categories = KeywordCategory.query.filter_by(is_active=True).all()
        
        for category in categories:
            # Получаем все ключевые слова для категории
            keywords = Keyword.query.filter_by(
                category_id=category.id,
                is_active=True
            ).all()
            
            # Создаем словарь для каждой категории
            self.keywords[category.code] = {
                'ru': [k.word_ru for k in keywords if k.word_ru],
                'en': [k.word_en for k in keywords if k.word_en],
                'tm': [k.word_tm for k in keywords if k.word_tm],
                'synonyms': [syn for k in keywords for syn in k.synonyms]
            }
    
    def process_resume(self, file_path: str, candidate) -> Optional[Dict]:
        """
        Обрабатывает резюме и сохраняет данные в модель кандидата.
        
        Args:
            file_path: Путь к файлу резюме.
            candidate: Объект модели кандидата.
            
        Returns:
            dict: Структурированные данные из резюме или None в случае ошибки.
        """
        try:
            # Извлекаем данные из резюме
            extracted_data = self.extract_data_from_resume(file_path)
            if not extracted_data:
                return None
            
            # Сохраняем текст резюме в модель кандидата
            candidate.resume_text = extracted_data["raw_text"]
            
            # Сохраняем структурированные данные
            candidate.resume_data = {
                "personal_info": extracted_data["personal_info"],
                "education": extracted_data["education"],
                "work_experience": extracted_data["work_experience"],
                "skills": extracted_data["skills"]
            }
            
            # Сохраняем изменения в базе данных
            db.session.commit()
            
            current_app.logger.info(f"Данные резюме успешно сохранены для кандидата {candidate.id}")
            
            return extracted_data
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при сохранении данных резюме: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    def extract_data_from_resume(self, file_path: str) -> Optional[Dict]:
        """
        Извлекает структурированные данные из резюме.
        
        Args:
            file_path: Путь к файлу резюме.
            
        Returns:
            dict: Структурированные данные из резюме или None в случае ошибки.
        """
        start_time = time.time()
        current_app.logger.info(f"Начало анализа резюме: {file_path}")
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            current_app.logger.error(f"Файл не существует: {file_path}")
            return None
        
        try:
            # Определяем тип файла
            extension = os.path.splitext(file_path)[1].lower()
            
            # Извлекаем текст в зависимости от типа файла
            if extension == '.pdf':
                raw_text = self._extract_from_pdf(file_path)
            elif extension in ['.doc', '.docx']:
                raw_text = self._extract_from_docx(file_path)
            elif extension in ['.jpg', '.jpeg', '.png']:
                raw_text = self._extract_from_image(file_path)
            else:
                current_app.logger.error(f"Неподдерживаемый формат файла: {extension}")
                return None
                
            if not raw_text:
                current_app.logger.error("Не удалось извлечь текст из файла")
                return None
                
            # Определяем язык текста и используем соответствующую модель
            doc = self._detect_language(raw_text)
            
            # Извлекаем структурированные данные
            structured_data = {
                "raw_text": raw_text,
                "personal_info": self._extract_personal_info(doc),
                "education": self._extract_education(doc),
                "work_experience": self._extract_experience(doc),
                "skills": self._extract_skills(doc)
            }
            
            execution_time = time.time() - start_time
            current_app.logger.info(f"Завершен анализ резюме, время выполнения: {execution_time:.2f} секунд")
            
            return structured_data
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при анализе резюме: {str(e)}", exc_info=True)
            return None
    
    def _detect_language(self, text: str) -> spacy.tokens.Doc:
        """
        Определяет язык текста и выбирает соответствующую модель.
        
        Args:
            text: Текст для анализа.
            
        Returns:
            spacy.tokens.Doc: Обработанный документ spaCy.
        """
        # Используем русскую модель для определения языка
        doc_ru = self.nlp_ru(text[:1000])  # Анализируем первые 1000 символов
        
        # Если в тексте много русских слов, используем русскую модель
        russian_chars = sum(1 for token in doc_ru if any(c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in token.text.lower()))
        if russian_chars > 10:  # Пороговое значение для определения русского текста
            return self.nlp_ru(text)
        else:
            return self.nlp_en(text)
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """
        Извлекает текст из PDF файла.
        
        Args:
            file_path: Путь к PDF файлу.
            
        Returns:
            str: Извлеченный текст.
        """
        text = ""
        pdf_document = fitz.open(file_path)
        
        for page in pdf_document:
            # Проверяем, содержит ли страница текст
            if page.get_text().strip():
                text += page.get_text()
            else:
                # Если текста нет, вероятно это отсканированная страница
                pix = page.get_pixmap()
                img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text += self.tesseract.image_to_string(img, lang='rus+eng')
        
        return text
    
    def _extract_from_docx(self, file_path: str) -> str:
        """
        Извлекает текст из DOCX файла.
        
        Args:
            file_path: Путь к DOCX файлу.
            
        Returns:
            str: Извлеченный текст.
        """
        doc = DocxDocument(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    def _extract_from_image(self, file_path: str) -> str:
        """
        Извлекает текст из изображения.
        
        Args:
            file_path: Путь к файлу изображения.
            
        Returns:
            str: Извлеченный текст.
        """
        img = PILImage.open(file_path)
        return self.tesseract.image_to_string(img, lang='rus+eng')
    
    def _extract_personal_info(self, doc: spacy.tokens.Doc) -> Dict:
        """
        Извлекает личную информацию из текста.
        
        Args:
            doc: Документ spaCy.
            
        Returns:
            dict: Извлеченная личная информация.
        """
        personal_info = {
            "full_name": "",
            "location": "",
            "phone": "",
            "email": "",
            "additional_contacts": []
        }
        
        # Извлекаем имена
        for ent in doc.ents:
            if ent.label_ == "PER":
                personal_info["full_name"] = ent.text
            elif ent.label_ == "GPE" or ent.label_ == "LOC":
                personal_info["location"] = ent.text
        
        # Ищем email и телефон с помощью регулярных выражений
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\+?[1-9]\d{10,14}'
        
        emails = re.findall(email_pattern, doc.text)
        phones = re.findall(phone_pattern, doc.text)
        
        if emails:
            personal_info["email"] = emails[0]
        if phones:
            personal_info["phone"] = phones[0]
        
        return personal_info
    
    def _extract_education(self, doc: spacy.tokens.Doc) -> Dict:
        """
        Извлекает информацию об образовании.
        
        Args:
            doc: Документ spaCy.
            
        Returns:
            dict: Извлеченная информация об образовании.
        """
        education = {
            "institutions": [],
            "degrees": [],
            "years": [],
            "highest_education": ""
        }
        
        # Получаем ключевые слова для образования
        edu_keywords = self.keywords.get('education', {})
        
        # Ищем организации, связанные с образованием
        for ent in doc.ents:
            if ent.label_ == "ORG":
                # Проверяем, содержит ли название организации ключевые слова
                text_lower = ent.text.lower()
                if any(edu_word in text_lower for edu_word in edu_keywords['ru'] + edu_keywords['en'] + edu_keywords['tm'] + edu_keywords['synonyms']):
                    education["institutions"].append(ent.text)
        
        # Ищем годы обучения
        year_pattern = r'20\d{2}|19\d{2}'
        years = re.findall(year_pattern, doc.text)
        if years:
            education["years"] = sorted(list(set(years)))
        
        return education
    
    def _extract_experience(self, doc: spacy.tokens.Doc) -> Dict:
        """
        Извлекает информацию об опыте работы.
        
        Args:
            doc: Документ spaCy.
            
        Returns:
            dict: Извлеченная информация об опыте работы.
        """
        experience = {
            "companies": [],
            "positions": [],
            "time_periods": [],
            "responsibilities": [],
            "total_years_experience": 0
        }
        
        # Получаем ключевые слова для должностей
        position_keywords = self.keywords.get('position', {})
        
        # Ищем компании
        for ent in doc.ents:
            if ent.label_ == "ORG":
                experience["companies"].append(ent.text)
        
        # Ищем должности
        for sent in doc.sents:
            text_lower = sent.text.lower()
            if any(pos in text_lower for pos in position_keywords['ru'] + position_keywords['en'] + position_keywords['tm'] + position_keywords['synonyms']):
                experience["positions"].append(sent.text.strip())
        
        return experience
    
    def _extract_skills(self, doc: spacy.tokens.Doc) -> Dict:
        """
        Извлекает информацию о навыках.
        
        Args:
            doc: Документ spaCy.
            
        Returns:
            dict: Извлеченная информация о навыках.
        """
        skills = {
            "technical_skills": [],
            "soft_skills": [],
            "languages": [],
            "certifications": []
        }
        
        # Получаем ключевые слова для разных типов навыков
        tech_keywords = self.keywords.get('technical_skill', {})
        soft_keywords = self.keywords.get('soft_skill', {})
        language_keywords = self.keywords.get('language', {})
        
        text_lower = doc.text.lower()
        
        # Ищем технические навыки
        for keyword in tech_keywords['ru'] + tech_keywords['en'] + tech_keywords['tm'] + tech_keywords['synonyms']:
            if keyword.lower() in text_lower:
                skills["technical_skills"].append(keyword)
        
        # Ищем софт-скиллы
        for keyword in soft_keywords['ru'] + soft_keywords['en'] + soft_keywords['tm'] + soft_keywords['synonyms']:
            if keyword.lower() in text_lower:
                skills["soft_skills"].append(keyword)
        
        # Ищем языки
        for keyword in language_keywords['ru'] + language_keywords['en'] + language_keywords['tm'] + language_keywords['synonyms']:
            if keyword.lower() in text_lower:
                skills["languages"].append(keyword)
        
        return skills
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import cv2
import numpy as np
import argparse
from PIL import Image
import matplotlib.pyplot as plt

# Добавляем путь к проекту в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем наши классы
from app.utils.image_processor import ImageProcessor
from app.utils.handwriting_recognizer import HandwritingRecognizer
from app.utils.form_analyzer import FormAnalyzer

def show_images(images, titles=None):
    """
    Отображает несколько изображений в одном окне
    """
    n = len(images)
    plt.figure(figsize=(15, 10))
    for i, img in enumerate(images):
        plt.subplot(1, n, i+1)
        plt.imshow(img, cmap='gray')
        if titles:
            plt.title(titles[i])
        plt.xticks([])
        plt.yticks([])
    plt.tight_layout()
    plt.show()

def test_image_processor(image_path):
    """
    Тестирует функции ImageProcessor
    """
    print("Тестирование ImageProcessor...")
    
    # Загружаем изображение
    img = cv2.imread(image_path)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Инициализируем процессор изображений
    processor = ImageProcessor()
    
    # Тестируем разные методы обработки
    enhanced = processor.enhance_contrast(img_gray)
    denoised = processor.remove_noise(img_gray)
    deskewed = processor.deskew(img_gray)
    binary = processor.adaptive_threshold(img_gray)
    
    # Применяем все методы вместе
    processed = processor.process_image(img_gray, methods=['all'])
    
    # Отображаем результаты
    show_images([img_gray, enhanced, denoised, deskewed, binary, processed],
               ['Оригинал', 'Улучшение контраста', 'Удаление шума', 'Коррекция наклона', 'Бинаризация', 'Все методы'])
    
    # Тестируем сегментацию текстовых блоков
    blocks = processor.segment_text_blocks(processed)
    print(f"Найдено {len(blocks)} текстовых блоков")
    
    if blocks:
        block_images = blocks[:min(5, len(blocks))]  # Берем первые 5 блоков
        show_images(block_images, [f'Блок {i+1}' for i in range(len(block_images))])
    
    return processed

def test_handwriting_recognizer(image_path):
    """
    Тестирует функции HandwritingRecognizer
    """
    print("Тестирование HandwritingRecognizer...")
    
    # Загружаем изображение
    img = cv2.imread(image_path)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Инициализируем распознаватель рукописного текста
    recognizer = HandwritingRecognizer()
    
    # Тестируем разные методы распознавания
    methods = ['adaptive', 'segmentation', 'multi_scale']
    results = {}
    
    for method in methods:
        print(f"Метод: {method}")
        text = recognizer.recognize(img_gray, method=method)
        print(f"Распознанный текст ({len(text)} символов):")
        print("-" * 50)
        print(text)
        print("-" * 50)
        results[method] = text
    
    return results

def test_form_analyzer(image_path):
    """
    Тестирует функции FormAnalyzer
    """
    print("Тестирование FormAnalyzer...")
    
    # Загружаем изображение
    img = cv2.imread(image_path)
    
    # Инициализируем анализатор форм
    analyzer = FormAnalyzer()
    
    # Автоматически определяем поля формы
    fields = analyzer.detect_form_fields(img)
    print(f"Найдено {len(fields)} полей формы")
    
    # Визуализируем найденные поля
    img_with_fields = img.copy()
    for name, (x, y, w, h) in fields.items():
        cv2.rectangle(img_with_fields, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(img_with_fields, name, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # Отображаем изображение с полями
    plt.figure(figsize=(10, 10))
    plt.imshow(cv2.cvtColor(img_with_fields, cv2.COLOR_BGR2RGB))
    plt.title('Обнаруженные поля формы')
    plt.axis('off')
    plt.show()
    
    # Извлекаем данные из формы
    form_data = analyzer.extract_form_data(img, form_type="resume")
    print("Извлеченные данные из формы:")
    for field, value in form_data.items():
        print(f"{field}: {value}")
    
    # Проверяем распознавание таблиц
    try:
        table_data = analyzer.extract_table(img)
        print(f"Найдена таблица размером {len(table_data)}x{len(table_data[0]) if table_data else 0}")
        for row in table_data:
            print(" | ".join(row))
    except Exception as e:
        print(f"Ошибка при распознавании таблицы: {str(e)}")
    
    # Обрабатываем как структурированный документ
    structured_data = analyzer.process_structured_document(img)
    print("Результаты обработки структурированного документа:")
    print(f"Найдено форм: {len(structured_data['forms'])}")
    print(f"Найдено таблиц: {len(structured_data['tables'])}")
    
    return structured_data

def main():
    parser = argparse.ArgumentParser(description='Тестирование функций распознавания текста')
    parser.add_argument('image_path', help='Путь к изображению для тестирования')
    parser.add_argument('--test', choices=['all', 'image', 'handwriting', 'form'], default='all',
                        help='Выберите тест для запуска')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Ошибка: файл {args.image_path} не существует")
        return
    
    if args.test in ['all', 'image']:
        processed_image = test_image_processor(args.image_path)
    
    if args.test in ['all', 'handwriting']:
        handwriting_results = test_handwriting_recognizer(args.image_path)
    
    if args.test in ['all', 'form']:
        form_results = test_form_analyzer(args.image_path)
    
    print("Тестирование завершено!")

if __name__ == "__main__":
    main()
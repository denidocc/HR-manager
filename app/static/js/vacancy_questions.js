// Глобальные массивы для хранения вопросов
var questions = [];
var softQuestions = [];

// Функция для добавления нового профессионального вопроса
function addQuestion(text = '', type = 'text') {
    const newId = questions.length > 0 ? Math.max(...questions.map(q => q.id)) + 1 : 1;
    questions.push({
        id: newId,
        text: text,
        type: type,
        options: []
    });
    renderQuestions();
    updateQuestionsJson();
}

// Функция для добавления нового вопроса на soft skills
function addSoftQuestion(text = '', type = 'text') {
    const newId = softQuestions.length > 0 ? Math.max(...softQuestions.map(q => q.id)) + 1 : 1;
    softQuestions.push({
        id: newId,
        text: text,
        type: type
    });
    renderSoftQuestions();
    updateSoftQuestionsJson();
}

// Функция для отрисовки профессиональных вопросов
function renderQuestions() {
    const container = document.getElementById('questionsContainer');
    if (!container) {
        console.error('Контейнер вопросов не найден!');
        return;
    }
    
    container.innerHTML = '';
    console.log('Рендеринг вопросов:', questions);
    
    if (!Array.isArray(questions)) {
        console.error('questions не является массивом при рендеринге:', questions);
        return;
    }
    
    questions.forEach((question, index) => {
        if (!question || typeof question !== 'object') {
            console.error(`Вопрос ${index+1} не является объектом:`, question);
            return;
        }
        
        // Экранируем HTML-символы в тексте вопроса
        const questionText = question.text || '';
        console.log(`Рендерим вопрос ${index+1}, текст:`, questionText);
        
        const questionHTML = `
            <div class="question-item border-bottom pb-3 mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">Вопрос ${index + 1}</h6>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeQuestion(${index})">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
                
                <div class="form-group mb-2">
                    <label class="form-label small">Текст вопроса</label>
                    <input type="text" class="form-control" value="${questionText}" 
                           onchange="updateQuestionText(${index}, this.value)">
                </div>
                
                <div class="form-group mb-2">
                    <label class="form-label small">Тип вопроса</label>
                    <select class="form-select" onchange="updateQuestionType(${index}, this.value)">
                        <option value="text" ${question.type === 'text' ? 'selected' : ''}>Текстовый ответ</option>
                        <option value="select" ${question.type === 'select' ? 'selected' : ''}>Один вариант из списка</option>
                        <option value="multiselect" ${question.type === 'multiselect' ? 'selected' : ''}>Несколько вариантов из списка</option>
                    </select>
                </div>
                
                ${(question.type === 'select' || question.type === 'multiselect') ? `
                    <div class="form-group">
                        <label class="form-label small">Варианты ответов (каждый с новой строки)</label>
                        <textarea class="form-control" rows="3" 
                                  onchange="updateQuestionOptions(${index}, this.value)">${(question.options || []).join('\n')}</textarea>
                    </div>
                ` : ''}
            </div>
        `;
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = questionHTML;
        container.appendChild(tempDiv.firstElementChild);
    });
    
    // Обновляем скрытое поле с JSON
    const jsonField = document.getElementById('questionsJsonField');
    if (!jsonField) {
        console.error('Поле JSON для вопросов не найдено!');
        return;
    }
    
    // Перед сохранением убедимся, что тексты вопросов сохранились
    for (let i = 0; i < questions.length; i++) {
        if (!questions[i].text) {
            console.warn(`Пустой текст в вопросе ${i+1} перед сохранением:`, questions[i]);
        }
    }
    
    jsonField.value = JSON.stringify(questions);
    console.log('Обновлено поле questionsJsonField:', jsonField.value);
}

// Функция для отрисовки вопросов на soft skills
function renderSoftQuestions() {
    const container = document.getElementById('softQuestionsContainer');
    if (!container) {
        console.error('Контейнер soft-вопросов не найден!');
        return;
    }
    
    container.innerHTML = '';
    console.log('Рендеринг soft-вопросов:', softQuestions);
    
    if (!Array.isArray(softQuestions)) {
        console.error('softQuestions не является массивом при рендеринге:', softQuestions);
        return;
    }
    
    softQuestions.forEach((question, index) => {
        if (!question || typeof question !== 'object') {
            console.error(`Soft-вопрос ${index+1} не является объектом:`, question);
            return;
        }
        
        // Экранируем HTML-символы в тексте вопроса
        const questionText = question.text || '';
        console.log(`Рендерим soft-вопрос ${index+1}, текст:`, questionText);
        
        const questionHTML = `
            <div class="question-item border-bottom pb-3 mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">Вопрос ${index + 1}</h6>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeSoftQuestion(${index})">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
                
                <div class="form-group mb-2">
                    <label class="form-label small">Текст вопроса</label>
                    <input type="text" class="form-control" value="${questionText}" 
                           onchange="updateSoftQuestionText(${index}, this.value)">
                </div>
            </div>
        `;
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = questionHTML;
        container.appendChild(tempDiv.firstElementChild);
    });
    
    // Обновляем скрытое поле с JSON
    const jsonField = document.getElementById('softQuestionsJsonField');
    if (!jsonField) {
        console.error('Поле JSON для soft-вопросов не найдено!');
        return;
    }
    
    // Перед сохранением убедимся, что тексты вопросов сохранились
    for (let i = 0; i < softQuestions.length; i++) {
        if (!softQuestions[i].text) {
            console.warn(`Пустой текст в soft-вопросе ${i+1} перед сохранением:`, softQuestions[i]);
        }
    }
    
    jsonField.value = JSON.stringify(softQuestions);
    console.log('Обновлено поле softQuestionsJsonField:', jsonField.value);
}

// Функции для обновления данных в массиве вопросов
function updateQuestionText(index, value) {
    questions[index].text = value;
    document.getElementById('questionsJsonField').value = JSON.stringify(questions);
}

function updateQuestionType(index, value) {
    questions[index].type = value;
    renderQuestions(); // Перерисовываем, чтобы показать/скрыть поле для вариантов
}

function updateQuestionOptions(index, value) {
    questions[index].options = value.split('\n').filter(o => o.trim() !== '');
    document.getElementById('questionsJsonField').value = JSON.stringify(questions);
}

function removeQuestion(index) {
    questions.splice(index, 1);
    renderQuestions();
}

// Функции для обновления данных в массиве soft-вопросов
function updateSoftQuestionText(index, value) {
    softQuestions[index].text = value;
    document.getElementById('softQuestionsJsonField').value = JSON.stringify(softQuestions);
}

function removeSoftQuestion(index) {
    softQuestions.splice(index, 1);
    renderSoftQuestions();
}

// Инициализация при загрузке страницы для страницы создания вакансии
function initCreateVacancy() {
    // Добавляем по одному пустому вопросу для начала
    if (questions.length === 0) {
        addQuestion();
    }
    
    if (softQuestions.length === 0) {
        addSoftQuestion();
    }
}

// Инициализация при загрузке страницы для страницы редактирования вакансии
function initEditVacancy() {
    try {
        const questionsField = document.getElementById('questionsJsonField');
        if (!questionsField) {
            console.error('Поле questionsJsonField не найдено!');
            questions = [];
            addQuestion();
            return;
        }
        
        // Получаем данные из value атрибута
        const questionsData = questionsField.value;
        console.log("Загружаю данные вопросов:", questionsData);
        
        if (questionsData && questionsData.trim() !== '' && questionsData !== '[]') {
            try {
                const parsed = JSON.parse(questionsData);
                console.log("Парсинг данных вопросов успешен:", parsed);
                
                // Проверяем и конвертируем в массив, если нужно
                if (Array.isArray(parsed)) {
                    questions = parsed;
                } else if (typeof parsed === 'object') {
                    console.log("Преобразование объекта в массив:", parsed);
                    questions = Array.isArray(parsed) ? parsed : [parsed];
                } else {
                    console.error("Данные не являются ни массивом, ни объектом:", parsed);
                    questions = [];
                    addQuestion();
                }
            } catch (e) {
                console.error("Ошибка парсинга JSON вопросов:", e);
                questions = [];
                addQuestion();
            }
            
            console.log("Финальный массив вопросов перед отрисовкой:", questions);
            renderQuestions();
        } else {
            console.log("Нет данных вопросов, добавляю пустой вопрос");
            questions = [];
            addQuestion();
        }
        
        const softQuestionsField = document.getElementById('softQuestionsJsonField');
        if (!softQuestionsField) {
            console.error('Поле softQuestionsJsonField не найдено!');
            softQuestions = [];
            return;
        }
        
        // Получаем данные из value атрибута
        const softQuestionsData = softQuestionsField.value;
        console.log("Загружаю данные soft-вопросов:", softQuestionsData);
        
        if (softQuestionsData && softQuestionsData.trim() !== '' && softQuestionsData !== '[]') {
            try {
                const parsed = JSON.parse(softQuestionsData);
                console.log("Парсинг данных soft-вопросов успешен:", parsed);
                
                // Проверяем и конвертируем в массив, если нужно
                if (Array.isArray(parsed)) {
                    softQuestions = parsed;
                } else if (typeof parsed === 'object') {
                    console.log("Преобразование объекта soft в массив:", parsed);
                    softQuestions = Array.isArray(parsed) ? parsed : [parsed];
                } else {
                    console.error("Данные soft не являются ни массивом, ни объектом:", parsed);
                    softQuestions = [];
                }
            } catch (e) {
                console.error("Ошибка парсинга JSON soft-вопросов:", e);
                softQuestions = [];
            }
            
            // Рендерим существующие вопросы
            if (softQuestions.length > 0) {
                renderSoftQuestions();
            }
        } else {
            console.log("Нет данных soft-вопросов");
            softQuestions = [];
        }
    } catch (e) {
        console.error("Общая ошибка при инициализации вопросов:", e, e.stack);
        // В случае ошибки, создаем пустые вопросы
        questions = [];
        softQuestions = [];
        addQuestion();
    }
}

// Функция для проверки и обновления JSON полей перед отправкой формы
function prepareFormSubmit() {
    // Проверяем наличие вопросов и обновляем скрытые поля
    const questionsField = document.getElementById('questionsJsonField');
    const softQuestionsField = document.getElementById('softQuestionsJsonField');
    
    console.log("Подготовка к отправке формы");
    console.log("Вопросы перед отправкой:", questions);
    console.log("Soft-вопросы перед отправкой:", softQuestions);
    
    // Проверяем наличие текста в вопросах
    for (let i = 0; i < questions.length; i++) {
        console.log(`Проверка вопроса ${i+1}:`, questions[i]);
        if (!questions[i].text) {
            // Получаем значение из DOM, на случай если JavaScript не обновил массив
            try {
                const inputField = document.querySelector(`#questionsContainer .question-item:nth-child(${i+1}) input[type="text"]`);
                if (inputField && inputField.value) {
                    console.log(`Восстановление текста вопроса ${i+1} из DOM:`, inputField.value);
                    questions[i].text = inputField.value;
                }
            } catch (e) {
                console.error("Ошибка при восстановлении текста вопроса из DOM:", e);
            }
        }
    }
    
    // Убедимся, что у нас есть последние данные
    if (questionsField && questions.length > 0) {
        questionsField.value = JSON.stringify(questions);
        console.log("Установлено значение для questionsJsonField:", questionsField.value);
    } else if (questionsField) {
        questionsField.value = "[]";
        console.log("Установлено пустое значение для questionsJsonField");
    }
    
    if (softQuestionsField && softQuestions.length > 0) {
        // Если есть мягкие навыки, проверяем их текст
        for (let i = 0; i < softQuestions.length; i++) {
            console.log(`Проверка soft-вопроса ${i+1}:`, softQuestions[i]);
            if (!softQuestions[i].text) {
                try {
                    const inputField = document.querySelector(`#softQuestionsContainer .question-item:nth-child(${i+1}) input[type="text"]`);
                    if (inputField && inputField.value) {
                        console.log(`Восстановление текста soft-вопроса ${i+1} из DOM:`, inputField.value);
                        softQuestions[i].text = inputField.value;
                    }
                } catch (e) {
                    console.error("Ошибка при восстановлении текста soft-вопроса из DOM:", e);
                }
            }
        }
        softQuestionsField.value = JSON.stringify(softQuestions);
        console.log("Установлено значение для softQuestionsJsonField:", softQuestionsField.value);
    } else if (softQuestionsField) {
        softQuestionsField.value = "[]";
        console.log("Установлено пустое значение для softQuestionsJsonField");
    }
    
    return true;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем наличие необходимых элементов
    const addQuestionBtn = document.getElementById('addQuestionBtn');
    const addSoftQuestionBtn = document.getElementById('addSoftQuestionBtn');
    const vacancyForm = document.getElementById('vacancyForm');
    
    // Определяем, на какой странице мы находимся
    const urlPath = window.location.pathname;
    
    if (urlPath.endsWith('/create')) {
        initCreateVacancy();
    } else if (urlPath.includes('/edit')) {
        initEditVacancy();
    }
    
    // Добавляем обработчики событий для кнопок
    if (addQuestionBtn) {
        addQuestionBtn.addEventListener('click', function() {
            addQuestion();
        });
    }
    
    if (addSoftQuestionBtn) {
        addSoftQuestionBtn.addEventListener('click', function() {
            addSoftQuestion();
        });
    }
    
    // Добавляем обработчик отправки формы
    if (vacancyForm) {
        vacancyForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Предотвращаем стандартную отправку формы
            
            // Обновляем JSON перед отправкой
            prepareFormSubmit();
            
            // Получаем значения скрытых полей
            const questionsJsonField = document.getElementById('questionsJsonField');
            const softQuestionsJsonField = document.getElementById('softQuestionsJsonField');
            
            console.log("Перед отправкой формы:");
            console.log("questionsJsonField.value:", questionsJsonField ? questionsJsonField.value : "не найден");
            console.log("softQuestionsJsonField.value:", softQuestionsJsonField ? softQuestionsJsonField.value : "не найден");
            
            // Создаём объект для отправки данных формы
            const formData = new FormData(vacancyForm);
            
            // Удаляем старые значения и добавляем новые, чтобы быть уверенными
            formData.delete('questions_json');
            formData.delete('soft_questions_json');
            
            // Добавляем данные JSON в formData
            const questionsValue = questionsJsonField ? questionsJsonField.value : "[]";
            const softQuestionsValue = softQuestionsJsonField ? softQuestionsJsonField.value : "[]";
            
            formData.append('questions_json', questionsValue);
            formData.append('soft_questions_json', softQuestionsValue);
            
            console.log("После подготовки FormData:");
            console.log("questions_json:", formData.get('questions_json'));
            console.log("soft_questions_json:", formData.get('soft_questions_json'));
            
            // Отправляем форму напрямую
            fetch(vacancyForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    return response.text().then(html => {
                        document.open();
                        document.write(html);
                        document.close();
                    });
                }
            })
            .catch(error => {
                console.error('Ошибка при отправке формы:', error);
                alert('Произошла ошибка при отправке формы. Пожалуйста, попробуйте снова.');
            });
        });
    }
});

// Функция для обновления JSON-поля с вопросами
function updateQuestionsJson() {
    const jsonField = document.getElementById('questionsJsonField');
    if (jsonField) {
        jsonField.value = JSON.stringify(questions);
        console.log('Обновлено поле questionsJsonField:', jsonField.value);
    }
}

// Функция для обновления JSON-поля с soft-вопросами
function updateSoftQuestionsJson() {
    const jsonField = document.getElementById('softQuestionsJsonField');
    if (jsonField) {
        jsonField.value = JSON.stringify(softQuestions);
        console.log('Обновлено поле softQuestionsJsonField:', jsonField.value);
    }
} 
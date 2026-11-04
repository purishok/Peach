# Lab 8. Big Data on AWS: the Uklon example
Дата виконання: 4 листопада 2026. Проєкт: Peach / payments.

## Статус роботи
Parts 2-4 виконані на реальних даних: Athena/Glue за весь жовтень, п'ять локальних Redpanda replay та Kinesis -> Firehose -> S3 -> Athena з Lambda/SNS. Усі запити, CSV, метрики й докази очищення додані. Справжній скриншот Athena Console для Part 4 додано як athena-console.png. Він містить SQL, статус Completed і всі чотири рядки результату. Додатковий cloud-query-export.png залишається окремо позначеним рендером API-експорту.

Погоджене відхилення: використано акаунт 985040259102, регіон eu-north-1. SCP p-0wjafcyv обох налаштованих акаунтів блокує потрібні сервіси у us-east-1. Приватний bucket: peach-lab8-985040259102-eu-north-1. Через відмову прямого CopyObject виконано анонімне завантаження публічного джерела та upload через AWS CLI. Перенесено всі 31 файли, 1260672849 байтів; розміри source/destination збігаються. Це не безкоштовне same-region копіювання з умови; метод і регіон явно задокументовані. Політики організації та чинний Peach не змінювалися.

Скриншот athena-console.png перевірено: видно акаунт 985040259102, Europe (Stockholm), SQL над streamed_events, Completed, runtime 441 ms, data scanned 1.24 MB і чотири рядки, що збігаються з CSV запиту 51754667-06cb-44df-854c-244a4262c465. Оригінальний PNG включений у пакет. Ця робота не завантажена в LMS автоматично.

## Part 0-1. Дві дороги даних Uklon
Затримка realtime на 10 хвилин робить координати водіїв і surge застарілими: призначення авто та ETA погіршуються, ціна реагує на попередній попит, алерти приходять запізно. Потрібні контроль lag, backpressure і безпечний fallback. Затримка batch на добу відкладає звіти та оновлення моделей; поточні поїздки можуть працювати далі, якщо операційний шлях незалежний.

GPS передається через тривале MQTT-з'єднання з IoT Core: мобільним клієнтам потрібні підтримка з'єднання, сесія й легкий протокол для частих повідомлень. Lambda є обробником подій, а не брокером постійних MQTT-з'єднань. Запуск Lambda для кожного ping додає виклики, затримку й витрати; вона може бути корисна для вибіркової валідації або подальших дій. Безперервні агрегації, watermark і стан краще винести у спеціальний stream processor.

Малий стартап спершу може прибрати SageMaker на користь простих ETA-евристик, Flink на користь простішого consumer, DMS на користь явно опублікованих подій застосунку, а BI-дашборди замінити SQL-звітами. Втрати: якість прогнозів, складні realtime-агрегації, повнота CDC та зручність self-service аналітики. Варто зберегти операційну базу, потрібні для matching позиції водіїв і дешевий raw-архів; точний набір визначає фактичне навантаження.

## Part 2. Athena SQL і Glue Crawler: результати
Athena обробила 3030197 подій: 1000000 унікальних invoiceId, 30197 точних дублікатів. events - invoices = 2030197 також включає законні переходи статусів. View payments має рівно 1000000 рядків, з них 60180 failure (6,018%). Понад 60 секунд запізнилися 60824 із 3030197 подій (2.0073%). Понад годину - 0 із 3030197 (0%). Це результати за весь жовтень; окремі числа Part 3 нижче стосуються лише 1 жовтня.

SQL містить DDL усіх 16 полів, partition dt, MSCK REPAIR, view payments, scale/lateness, CTAS у Snappy Parquet та запити для обох форматів. Збережені реальні QueryExecutionId, CSV і Statistics; reuse результатів вимкнений. 02_payments_check/sample.csv підтверджують dedup; 03_turnover_json/parquet.csv містять усі 30 merchant/currency рядків; 04_failure_json/parquet.csv - 12 method/device комбінацій; 05_hours_json/parquet.csv - усі 24 години; 06_late.csv - обидва lateness пороги. JSON і Parquet CSV повністю збігаються.

Найбільший UAH turnover: Інтернет-магазин - 310259259,21 грн; АЗС - 144641341,06 грн; Квитки - 77749863,65 грн. Найвищий failure rate: qr/android, 448 із 6675 = 6,7116%. Пік кількості платежів: 18:00-18:59 UTC, 80338 платежів.

Turnover рахується лише для success з finalAmount / 100 у decimal, окремо за merchant та ccy; UAH, USD і EUR не додаються в одну суму. Failure rate: failure / (success + failure), окремо за paymentMethod і device. Peak hours: кількість унікальних платежів за годиною createdDate у UTC. Lateness читає raw-події та містить обидва пороги із завдання: понад 60 секунд і понад годину.

Чому DISTINCT перед row_number(): DISTINCT прибирає однакові raw-рядки до нумерації. Якщо включити row_number у той самий SELECT DISTINCT, копії отримають різні номери й перестануть бути однаковими для DISTINCT. Окремий row_number з rn=1 усе одно здатний залишити один рядок на invoice навіть без попереднього DISTINCT; у такому разі результат не обов'язково неправильний, але ranking виконує зайву роботу. Без вибору останнього статусу один платіж рахується 2-3 рази, created/processing спотворюють знаменник failure rate, а дубль success завищує turnover.

View спершу прибирає точні копії, потім вибирає останній modifiedDate для invoiceId по всіх днях. При однаковому часі застосовує стабільні tie breakers. Підрахунок events - unique invoices не є кількістю точних дублікатів: він також містить законні переходи статусів.

Crawler створив crawler_payments: amount/finalamount/ccy - int; createddate/modifieddate/receivedat - string; dt - string partition, усі 31 дні розпізнані. failureReason збережено як string: воно непорожнє для 60779 failed events, а для решти подій NULL; unexpected_reasons = 0. Відсутній ключ не видалив поле зі схеми. Ручний amount/finalamount bigint зручніший як стабільний контракт для грошей і запасу від переповнення int; ccy int доречний в обох варіантах. Дати обидві схеми лишили string, тож SQL явно парсить ISO timestamps. Metadata recordCount crawler є оцінкою з sampling; точні 3030197 отримано через COUNT, а не з цієї оцінки.

Нижче DataScannedInBytes та повний TotalExecutionTime у секундах. EngineExecutionTime окремо збережено в athena-comparison.csv і execution JSON. Scan x - зменшення читання; Bill x - відношення оцінки SQL-оплати з округленням до MB і мінімумом 10 MB. Результати виміряні одним запуском кожного запиту, тому runtime залежить також від планування та cold/warm стану сервісу.

| Запит | JSON bytes | Parquet bytes | JSON с | Parquet с | Scan x | Bill x |
|---|---|---|---|---|---|---|
| turnover | 1260692423 | 6389672 | 3.282 | 1.410 | 197.3 | 120.3 |
| failure | 1260692423 | 675513 | 4.190 | 1.747 | 1866.3 | 120.3 |
| hours | 1260692423 | 6545829 | 3.986 | 1.299 | 192.6 | 120.3 |

Кожен JSON-запит оцінено у $0,00573635, кожен Parquet - $0,00004768 при $5/TiB: приблизно у 120,3 рази дешевше. Сканування скоротилося сильніше, але всі три Parquet-запити менші за billing minimum 10 MB. Порівнюється JSON із dedup на читанні та вже очищений Parquet, тому виграш включає попереднє обчислення й формат. CTAS також має ціну сканування та запису.

## Part 3. Реальний dataset і методика
Використано файл payments/dt=2026-10-01/events.jsonl з наданого публічного S3. Він містить 101084 події, 33361 унікальний invoiceId і 1001 точний дублікат. Останні статуси без watermark-відсікання: 31371 success та 1990 failure. Понад 60 секунд запізнилися 2019 із 101084 подій (1,9973%); понад годину - 0 (0%). Це вимірювання тільки за 1 жовтня, не за весь місяць.

Redpanda має один broker, topic має 3 partitions, ключ повідомлення - invoiceId. Producer сортує день за receivedAt. Швидкість за замовчуванням перевірено на 100 справжніх платежах: 303 події за 5,002 с, тобто 20 payments/s. Повні replay прискорені: baseline/failure30/wait0 - 2000 payments/s, restart - 400, два consumers - 700. Історичні timestamps не змінюються; пауза consumer триває справжні 60 секунд.

Вікно - одна хвилина modifiedDate UTC, watermark - мінімальний maximum event time серед трьох партицій мінус grace. При grace=120 закривається вікно, кінець якого не пізніше watermark. Це очікування у відтвореному event time, не дві хвилини настінного часу. Наприкінці скінченного replay решта вікон явно фіналізується після завершення producer та consumers.

| Експеримент | Прочитано | Дублі | Late | Платежі | Невдачі | Частка | Alert-вікна |
|---|---|---|---|---|---|---|---|
| Базовий, 120 с | 101084 | 1001 | 1613 | 32819 | 1971 | 6.01% | 909 |
| Зупинка на 60 с | 101084 | 1001 | 884 | 33072 | 1977 | 5.98% | 909 |
| Два consumers | 101084 | 1001 | 1639 | 32808 | 1971 | 6.01% | 910 |
| 30% невдач | 101084 | 1001 | 1634 | 32812 | 9825 | 29.94% | 3232 |
| Очікування 0 с | 101084 | 1001 | 2013 | 32676 | 1964 | 6.01% | 911 |

Alert-вікно - одна пара minute/paymentMethod з failure share строго понад 10%. Не кожен алерт означає масовий інцидент: у маленькому вікні одна невдача може дати 50% або 100%. Загальна кількість непорожніх вікон відповідно: 4432, 4434, 4431, 4431, 4428.

## Part 3. Що змінилося і чому
Пауза. Після зупинки consumer lag становив 27 подій. Через 60,004 с перед відновленням - 72759. Після дочитування - 0; кінцеві offsets точно дорівнюють high-water offsets: 33629 / 33088 / 34367. Кожний повний експеримент прочитав усі 101084 події. Це підтверджує збереження log під час паузи; late rejection є політикою вікон, а не втратою з Kafka.

Два consumers. Знімок rpk group describe показує Stable, MEMBERS=2: consumer one має partitions 0 і 1, consumer two - partition 2. Кожен запис отримує один member цієї групи. Вони використовують спільний SQLite WAL на одному ноутбуці; це не розподілений state backend.

30% невдач. SHA-256(invoiceId) modulo 100 визначає terminal failure приблизно для 30% платежів. На рахованих платежах отримано 9825 / 32812 = 29,94%, alert-вікон 3232 проти 909 у baseline. Усі точні копії одного платежу змінюються однаково. Початковий файл не змінюється.

Нульове очікування. Late зросло з 1613 до 2013 (+400 подій). Рахованих terminal payments стало на 143 менше, failures - на 7 менше; частка змінилася з 6,0057% до 6,0105%, alert-вікон стало 911 проти 909. Змінилися 138 minute/method вікон; детальні before/after у window-differences.csv. Приклад: card, вікно epoch 1790814960, total 3 -> 2, failures 1 -> 1, частка 33,33% -> 50%. Відхилені late включають також created/processing, тому +400 подій не дорівнює -400 terminal payments.

Числа restart/two не абсолютно тотожні baseline. Kafka зберігає порядок усередині партиції, але не глобальний receivedAt-порядок між партиціями. Watermark через мінімум прогресу партицій залежить від interleaving і backlog. Після catch-up відстаюча партиція довше утримує watermark, тому більше пізніх записів ще встигає. Пауза дала 33072 рахованих платежі проти 32819 baseline; це пояснюється прийняттям late, а не повторним рахунком дублів. Для детермінованого offline-порівняння потрібен явно узгоджений порядок/watermark schedule.

Надійність і межі. SQLite транзакція містить state та next offset; після неї комітиться Kafka offset. При assignment consumer читає next offset зі state. Шість семантичних тестів пройшли, включно з recovery/dedup та mocked Lambda alert. Вивід stdout і SNS не є exactly-once: для них потрібні outbox/idempotency. seen/invoice/windows у навчальній версії ростуть безмежно. Production TTL треба узгодити з watermark, максимальною затримкою, replay horizon та checkpoint recovery; надто раннє очищення дозволить старому дублю порахуватися знову.

## Part 4. Виконаний хмарний pipeline
Діаграма додана як pipeline.svg і pipeline.mmd. Виконано: справжні події -> Python -> Kinesis, 1 provisioned shard -> Firehose -> приватний S3 stream/ -> Glue Catalog + Athena. Паралельно Kinesis -> Lambda -> SNS, із MessageId у CloudWatch. Producer взяв перші 3000 подій дня за receivedAt з ін'єкцією 30% failures: Kinesis прийняв 3000/3000, Athena потім прочитала рівно 3000. Sample охоплює 989 invoiceId; 988 мають terminal status, один ще проміжний на межі sample.

Athena query ID: 51754667-06cb-44df-854c-244a4262c465. Прочитано 1296129 байтів, engine time 441 ms, total time 596 ms. Усього 295 failures із 988 terminal payments (29.8583%). Це менший sample, тому його частка не має точно збігатися з 29,94% повного локального failure30 replay.

| Метод | Terminal payments | Failures | Failure share |
|---|---|---|---|
| apple_pay | 243 | 73 | 30.04% |
| card | 552 | 176 | 31.88% |
| google_pay | 166 | 41 | 24.70% |
| qr | 27 | 5 | 18.52% |

Lambda опублікувала 4 SNS alerts, по одному на кожен метод; їхні чисельники та знаменники збігаються з таблицею. Message IDs збережені в cloud-alerts.json. SNS topic не мав зовнішніх subscribers: демонструвався publish без повідомлень людям. Arrival-time вікно: 2026-11-04 15:29:00-15:30:00 UTC; payload event time у цих подій належить 1 жовтня.

Повну доставку перевірено до cleanup. cloud-cleanup.json та незалежна cleanup-verification.json підтверджують відсутність Kinesis, Firehose, Lambda, SNS і тимчасових IAM roles; crawler configuration теж видалена після експорту історії. Raw/Parquet/stream дані, Glue tables і журнали залишені для перевірки. Знімок AWS Console athena-console.png додано й перевірено за SQL, результатом та runtime; cloud-query-export.png є окремим позначеним рендером SQL/CSV/metadata.

Порівняння з Part 3. Kinesis замінює самостійно запущений Kafka-compatible broker, Firehose керує буферизацією й доставкою у S3, Athena читає архів SQL-запитами. У local group партиції розподіляються між members; Kinesis/Lambda має іншу модель споживання shard. Lambda tumbling windows використовують час вставлення в Kinesis, не payload modifiedDate; цей replay історичних даних тому дасть інші вікна. Щоб повторити event-time grace та state Part 3 у cloud, потрібен, наприклад, Flink з відповідними watermark і checkpoint. В обох дорогах deduplication потрібна окремо.

## Витрати та збережені ресурси
Тарифи eu-north-1 отримано з AWS Price List API. Оцінка компонентів за метриками використання: приблизно $0.1278 до credits/taxes, не остаточний AWS invoice. З них усі 27 Athena executions - $0.057979; Kinesis оцінено консервативно за одну shard-hour - $0.0162, PUT - $0.0000471; Firehose - $0.000421. Kinesis існував менше 271 с, після видалення shard charges не продовжуються.

Crawler повідомив 0.120666 DPU-hour: проста usage-based оцінка $0.053093. Це не тотожне кінцевому billing: AWS Glue FAQ вказує мінімум 10 хвилин на crawl. Для ілюстрації, при 2 DPUs і цьому мінімумі crawler коштував би $0.146667, а сума перелічених компонентів - приблизно $0.2213. Кількість 2 DPUs тут є припущенням сценарію, не виміряним allocation. Остаточний рахунок треба перевірити після його появи в billing.

31 Lambda invocation, billed duration 2639 ms при 128 MB, та 4 SNS publishes додають дуже малі суми до free tier. Залишені S3-файли мають оцінку приблизно $0.0288/місяць за зберігання. У наведені totals не включено S3 requests, CloudWatch logs, остаточні billing minimums, витрати на публічне source-завантаження/локальну мережу та податки. Перенесення між регіонами не називається безкоштовним. Локальний Redpanda не має погодинної AWS-плати.

## Обговорення в класі
Event time описує, коли подія сталася в бізнесі; processing/received time - коли її побачила система. Late event може змінити ще відкрите вікно або бути відкинутим після watermark. JSON зберігає raw-історію для аудиту, replay і виправлення помилок; Parquet містить компактні очищені аналітичні дані для дешевого колонкового читання. Нічний batch достатній для місячної звітності, але matching, surge та fraud alerts потребують секунд. Managed services знімають частину роботи з масштабування, відмовостійкості й експлуатації; натомість мають service-specific API, обмеження, ціну та залежність від провайдера. Бізнес-семантику вікон, даних і дедуплікації вони не визначають замість розробника.

## Матеріали й джерела
code.zip: source, README, SQL та тести. evidence.zip: фактичні Athena CSV/executions, crawler schema/history, порівняння scan/runtime/cost, cloud receipts/SNS/cleanup, consumer/producer logs, window CSV, lifecycle/offsets, group membership і tests.log. Великі raw-дані, SQLite state, credentials та віртуальне середовище не включені. Для LMS достатньо 4 файлів: цей PDF, code.zip, evidence.zip та athena-console.png; діаграма вже вкладена в evidence.zip. online-text.txt призначено для текстового поля.

AWS Athena CTAS: https://docs.aws.amazon.com/athena/latest/ug/ctas-considerations-limitations.html
Lambda Kinesis windows: https://docs.aws.amazon.com/lambda/latest/dg/services-kinesis-windows.html
Glue crawlers: https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html
Kinesis pricing: https://aws.amazon.com/kinesis/data-streams/pricing/
Firehose pricing: https://aws.amazon.com/firehose/pricing/
Glue billing minimum: https://aws.amazon.com/glue/faqs/

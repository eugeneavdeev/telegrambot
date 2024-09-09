from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
import re
import os
import paramiko
import psycopg2
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')

db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')

async def start(update: Update, context):
    user = update.effective_user
    await update.message.reply_text('/connect_ssh - команда для подключения к ВМ')

async def connect_ssh_command(update: Update, context):
    await update.message.reply_text('Введите данные через пробел: ip port user password')
    return 'ssh_connect'

async def ssh_connect(update: Update, context):
    text = update.message.text
    try:
        ip, port, username, password = text.split()        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, int(port), username, password, timeout=10)
        client.close()
        context.user_data['ssh'] = {'ip': ip, 'port': int(port), 'username': username, 'password': password}
        await update.message.reply_text('Подключено!')
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text('Ошибка ввода')
        return 'ssh_connect'
    except Exception as e:
        await update.message.reply_text(f'Ошибка подключения: {str(e)}')
        return 'ssh_connect'

def ssh_command(context, command):
    ssh_data = context.user_data.get('ssh', {})
    if not ssh_data:
        return "Используйте команду /connect_ssh для подключения к ВМ и дальнейшему использованию комманд "
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ssh_data['ip'], ssh_data['port'], ssh_data['username'], ssh_data['password'])
    stdin, stdout, stderr = client.exec_command(command)
    result = stdout.read() + stderr.read()
    client.close()
    return result.decode()

def save_to_database(data_list, table_name, column_name):    
    connection = psycopg2.connect(user=db_user, password=db_password, host=db_host, port=db_port, database=db_name)
    cursor = connection.cursor()
    try:
        for data in data_list:
            query = f"INSERT INTO {table_name} ({column_name}) VALUES (%s)"
            cursor.execute(query, (data,))
        connection.commit()
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

async def findEmailsCommand(update: Update, context):
    await update.message.reply_text('Введите текст')
    return FIND_EMAILS

async def findEmails(update: Update, context):
    user_input = update.message.text
    emailRegex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    emailList = emailRegex.findall(user_input)
    if not emailList:
        await update.message.reply_text('Email(s) не найдены')
        return ConversationHandler.END
    context.user_data['emails'] = emailList
    emails = '\n'.join([f'{i+1}. {email}' for i, email in enumerate(emailList)])
    await update.message.reply_text(emails)
    await update.message.reply_text('Сохранить в БД? да/нет')
    return SAVE_EMAILS

async def saveEmails(update: Update, context):
    if update.message.text.lower() == 'да':
        if save_to_database(context.user_data.get('emails', []), 'email', 'email'): 
            await update.message.reply_text('Email(s) сохранены.')
        else:
            await update.message.reply_text('Ошибка')
    else:
        await update.message.reply_text('Отменено')
    return ConversationHandler.END

async def findPhoneNumbersCommand(update: Update, context):
    await update.message.reply_text('Введите текст:')
    return FIND_PHONE_NUMBERS

async def findPhoneNumbers(update: Update, context):
    user_input = update.message.text
    phoneNumRegex = re.compile(r'(\+7|8)[- ]?(\(?\d{3}\)?[- ]?\d{3}[- ]?\d{2}[- ]?\d{2})')
    phoneNumberList = phoneNumRegex.findall(user_input)
    if not phoneNumberList:
        await update.message.reply_text('Номера не найдены')
        return ConversationHandler.END
    context.user_data['phone_numbers'] = [''.join(num) for num in phoneNumberList]  
    phoneNumbers = '\n'.join([f'{i+1}. {num}' for i, num in enumerate(context.user_data['phone_numbers'])])
    await update.message.reply_text(f'Результат:\n{phoneNumbers}')
    await update.message.reply_text('Сохранить в БД? да/нет')
    return SAVE_PHONE_NUMBERS

async def savePhoneNumbers(update: Update, context):
    user_response = update.message.text.lower()
    if user_response == 'да':
        if save_to_database(context.user_data.get('phone_numbers', []), 'phone', 'phone'):
            await update.message.reply_text('Номера сохранены')
        else:
            await update.message.reply_text('Ошибка')
    else:
        await update.message.reply_text('Отменено')
    return ConversationHandler.END

async def get_email(update: Update, context):
    connection = psycopg2.connect(user=db_user, password=db_password, host=db_host, port=db_port, database=db_name)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT email FROM email")
        emails = cursor.fetchall()
        if emails:
            email_text = '\n'.join([email[0] for email in emails])
            await safe_send_message(update, f"Email адреса в БД:\n{email_text}")
        else:
            await update.message.reply_text('В БД нет email-адресов')
    finally:
        cursor.close()
        connection.close()

async def get_phone(update: Update, context):
    connection = psycopg2.connect(user=db_user, password=db_password, host=db_host, port=db_port, database=db_name)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT phone FROM phone")
        phones = cursor.fetchall()
        if phones:
            phone_text = '\n'.join([phone[0] for phone in phones])
            await safe_send_message(update, f"Телефонные номера:\n{phone_text}")
        else:
            await update.message.reply_text('В БД нет номеров')
    finally:
        cursor.close()
        connection.close()

PASSWORD_ENTRY = 'password_entry'
async def verify_password_command(update: Update, context):
    await update.message.reply_text('Введите пароль:')
    return PASSWORD_ENTRY

async def verify_password(update: Update, context):
    password = update.message.text    
    password_regex = re.compile(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$')
    if password_regex.match(password):
        await update.message.reply_text('Пароль сложный')
    else:
        await update.message.reply_text('Пароль простой')
    return ConversationHandler.END

async def safe_send_message(update: Update, text: str, max_length=4096):   
    if len(text) <= max_length:
        await update.message.reply_text(text)
    else:
        for start in range(0, len(text), max_length):
            await update.message.reply_text(text[start:start + max_length])

async def get_release(update: Update, context):
    command = "lsb_release -a"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Информация о релизе:\n{result}")

async def get_uname(update: Update, context):
    command = "uname -a"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Информация о системе:\n{result}")

async def get_uptime(update: Update, context):
    command = "uptime"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Время работы системы:\n{result}")

async def get_df(update: Update, context):
    command = "df -h"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Состояние файловой системы:\n{result}")

async def get_free(update: Update, context):
    command = "free -h"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Состоянии оперативной памяти:\n{result}")

async def get_mpstat(update: Update, context):
    command = "mpstat"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Производительность системы:\n{result}")

async def get_w(update: Update, context):
    command = "w"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Активные пользователи в системе:\n{result}")

async def get_auths(update: Update, context):
    command = "last -n 10"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Последние 10 входов в систему:\n{result}")

async def get_critical(update: Update, context):
    command = "journalctl -p crit -n 5"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Последние 5 критических события:\n{result}")

async def get_ps(update: Update, context):
    command = "ps -aux"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Запущенные процессы:\n{result}")

async def get_ss(update: Update, context):
    command = "ss -tulwn"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Используемые порты:\n{result}")

async def get_apt_list(update: Update, context):
    args = context.args
    package_name = ' '.join(args) if args else ''
    command = f"apt list --installed | grep {package_name}" if package_name else "apt list --installed"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Установленные пакеты:\n{result}")

async def get_services(update: Update, context):
    command = "systemctl list-units --type=service --state=running"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Запущенные сервисы:\n{result}")

async def get_repl_logs(update: Update, context):
    command = "tail -n 100 /var/lib/docker/volumes/*_master_data/_data/logs/*.log"
    result = ssh_command(context, command)
    await safe_send_message(update, f"Логи репликации:\n{result}")

async def cancel(update: Update, context):
    await update.message.reply_text('Действие отменено.')
    return ConversationHandler.END

async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

(FIND_EMAILS, SAVE_EMAILS, FIND_PHONE_NUMBERS, SAVE_PHONE_NUMBERS) = range(4)

def main():
    app = Application.builder().token(TOKEN).build()    
    convHandlerFindPhoneNumbers = ConversationHandler(
        entry_points=[CommandHandler('findPhoneNumbers', findPhoneNumbersCommand)],
        states={
            FIND_PHONE_NUMBERS: [MessageHandler(filters.Text() & ~filters.Command(), findPhoneNumbers)],
            SAVE_PHONE_NUMBERS: [MessageHandler(filters.Text() & ~filters.Command(), savePhoneNumbers)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    convHandlerFindEmails = ConversationHandler(
        entry_points=[CommandHandler('findEmails', findEmailsCommand)],
        states={
            FIND_EMAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, findEmails)],
            SAVE_EMAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, saveEmails)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    conv_handler_verify_password = ConversationHandler(
        entry_points=[CommandHandler('verify_password', verify_password_command)],
        states={
            PASSWORD_ENTRY: [MessageHandler(filters.Text() & ~filters.Command(), verify_password)]
        },
        fallbacks=[]
    )
    conv_handler_connect_ssh = ConversationHandler(
        entry_points=[CommandHandler('connect_ssh', connect_ssh_command)],
        states={'ssh_connect': [MessageHandler(filters.Text() & ~filters.Command(), ssh_connect)]},
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler("start", start))    
    app.add_handler(convHandlerFindPhoneNumbers)
    app.add_handler(convHandlerFindEmails)
    app.add_handler(conv_handler_verify_password)
    app.add_handler(conv_handler_connect_ssh)
    app.add_handler(CommandHandler("get_release", get_release))
    app.add_handler(CommandHandler("get_uname", get_uname))
    app.add_handler(CommandHandler("get_uptime", get_uptime))
    app.add_handler(CommandHandler("get_df", get_df))
    app.add_handler(CommandHandler("get_free", get_free))
    app.add_handler(CommandHandler("get_mpstat", get_mpstat))
    app.add_handler(CommandHandler("get_w", get_w))
    app.add_handler(CommandHandler("get_auths", get_auths))
    app.add_handler(CommandHandler("get_critical", get_critical))
    app.add_handler(CommandHandler("get_ps", get_ps))
    app.add_handler(CommandHandler("get_ss", get_ss))
    app.add_handler(CommandHandler("get_apt_list", get_apt_list))
    app.add_handler(CommandHandler("get_services", get_services))
    app.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    app.add_handler(CommandHandler("get_email", get_email))
    app.add_handler(CommandHandler("get_phone", get_phone))      
    app.add_handler(MessageHandler(filters.Text() & ~filters.Command(), echo))     
    app.run_polling()

if __name__ == '__main__':
    main()

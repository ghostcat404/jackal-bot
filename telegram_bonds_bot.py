#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import time
import urllib.request
import urllib.error
import urllib.parse
import datetime
import socket
import top_bonds
from dotenv import load_dotenv

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram bot token
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Telegram Bot API hostname and fallback IP
TELEGRAM_API_HOST = "api.telegram.org"
TELEGRAM_API_FALLBACK_IPS = ["149.154.167.220", "149.154.167.222"]  # Известные IP-адреса API Telegram

# Function to get API URL with fallback to direct IP if needed
def get_api_url():
    """Get the Telegram API URL, with fallback to direct IP if DNS resolution fails."""
    # First try the standard hostname
    try:
        # Try to resolve the hostname to verify DNS is working
        socket.gethostbyname(TELEGRAM_API_HOST)
        return "https://{}/bot{}/".format(TELEGRAM_API_HOST, BOT_TOKEN)
    except socket.gaierror as e:
        # DNS resolution failed, try fallback IPs
        logger.warning("DNS resolution failed for {}: {}. Using fallback IP.".format(
            TELEGRAM_API_HOST, e))
        
        # Try each fallback IP
        for ip in TELEGRAM_API_FALLBACK_IPS:
            try:
                # Test if we can connect to this IP
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(3)
                test_socket.connect((ip, 443))
                test_socket.close()
                
                # If we get here, connection was successful
                logger.info("Using fallback IP: {}".format(ip))
                # Use the IP directly but set the Host header to the original hostname
                return "https://{}/bot{}/".format(ip, BOT_TOKEN)
            except (socket.error, socket.timeout) as e:
                logger.warning("Failed to connect to fallback IP {}: {}".format(ip, e))
        
        # If all fallbacks failed, return the original URL as a last resort
        logger.error("All fallback IPs failed. Using original hostname as last resort.")
        return "https://{}/bot{}/".format(TELEGRAM_API_HOST, BOT_TOKEN)

# Telegram Bot API base URL (will be determined dynamically)
API_URL = None  # Will be initialized in main()

# Add Host header to requests when using direct IP
def add_host_header(req):
    """Add Host header to requests when using direct IP."""
    # Check if the URL contains an IP address
    if any(ip in req.get_full_url() for ip in TELEGRAM_API_FALLBACK_IPS):
        req.add_header('Host', TELEGRAM_API_HOST)
    return req

# Store subscribed users
subscribed_users = set()

# Last time bonds data was fetched
last_fetch_time = None
last_bonds_data = None

# Bot start time
start_time = time.time()

def send_message(chat_id, text, parse_mode=None):
    """Send a message to a Telegram chat."""
    url = API_URL + "sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    
    if parse_mode:
        data["parse_mode"] = parse_mode
    
    # Convert data to JSON
    data = json.dumps(data).encode('utf-8')
    
    # Create request
    req = urllib.request.Request(url, data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    req = add_host_header(req)  # Add Host header if needed
    
    # Maximum number of retries
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # Initial delay in seconds
    
    while retry_count < max_retries:
        try:
            # Create a context that doesn't verify SSL certificates
            import ssl
            context = ssl._create_unverified_context()
            
            # Send request with SSL context
            response = urllib.request.urlopen(req, context=context, timeout=10)
            return json.loads(response.read().decode('utf-8'))
        
        except urllib.error.URLError as e:
            # Network-related errors
            logger.error("Network error sending message (attempt {}/{}): {}".format(
                retry_count + 1, max_retries, e))
            
            # Increase retry count and delay
            retry_count += 1
            if retry_count < max_retries:
                logger.info("Retrying in {} seconds...".format(retry_delay))
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Maximum retries reached. Giving up.")
                return None
        
        except Exception as e:
            # Other errors
            logger.error("Error sending message: {}".format(e))
            return None

def delete_webhook():
    """Delete any existing webhook."""
    url = API_URL + "deleteWebhook?drop_pending_updates=true"
    
    # Create request
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    req = add_host_header(req)  # Add Host header if needed
    
    # Maximum number of retries
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # Initial delay in seconds
    
    while retry_count < max_retries:
        try:
            # Create a context that doesn't verify SSL certificates
            import ssl
            context = ssl._create_unverified_context()
            
            # Send request with SSL context
            response = urllib.request.urlopen(req, context=context, timeout=10)
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get("ok"):
                logger.info("Webhook deleted successfully and pending updates dropped")
            else:
                logger.error("Failed to delete webhook: {}".format(result.get("description")))
            
            return result
        
        except urllib.error.URLError as e:
            # Network-related errors
            logger.error("Network error deleting webhook (attempt {}/{}): {}".format(
                retry_count + 1, max_retries, e))
            
            # Increase retry count and delay
            retry_count += 1
            if retry_count < max_retries:
                logger.info("Retrying in {} seconds...".format(retry_delay))
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Maximum retries reached. Giving up.")
                return None
        
        except Exception as e:
            # Other errors
            logger.error("Error deleting webhook: {}".format(e))
            return None

def get_updates(offset=None):
    """Get updates from Telegram Bot API."""
    url = API_URL + "getUpdates"
    data = {}
    
    if offset:
        data["offset"] = offset
    
    # Convert data to JSON if needed
    if data:
        data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data)
        req.add_header('Content-Type', 'application/json')
    else:
        req = urllib.request.Request(url)
    
    # Add User-Agent header to mimic a browser
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    req = add_host_header(req)  # Add Host header if needed
    
    # Maximum number of retries
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # Initial delay in seconds
    
    while retry_count < max_retries:
        try:
            # Create a context that doesn't verify SSL certificates
            import ssl
            context = ssl._create_unverified_context()
            
            # Send request with SSL context
            response = urllib.request.urlopen(req, context=context, timeout=10)
            return json.loads(response.read().decode('utf-8'))
        
        except urllib.error.URLError as e:
            # Network-related errors
            logger.error("Network error getting updates (attempt {}/{}): {}".format(
                retry_count + 1, max_retries, e))
            
            # Increase retry count and delay
            retry_count += 1
            if retry_count < max_retries:
                logger.info("Retrying in {} seconds...".format(retry_delay))
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Maximum retries reached. Giving up.")
                return None
        
        except Exception as e:
            # Other errors
            logger.error("Error getting updates: {}".format(e))
            return None

def get_bonds_data(count=5):
    """
    Get bonds data and cache it.
    
    Args:
        count: Number of top bonds to return (default: 5)
    """
    global last_fetch_time, last_bonds_data
    
    # Check if we have cached data that's less than 1 hour old
    current_time = time.time()
    if last_fetch_time and last_bonds_data and current_time - last_fetch_time < 3600:
        # If we have enough bonds in the cache, return them
        if len(last_bonds_data) >= count:
            return last_bonds_data[:count]
        # Otherwise, we need to fetch more bonds
    
    try:
        # Get fresh data - fetch at least the requested number of bonds (max 20)
        fetch_count = max(count, 5)  # Always fetch at least 5
        fetch_count = min(fetch_count, 20)  # But no more than 20
        
        bonds = top_bonds.get_top_yield_bonds(fetch_count)
        if bonds and len(bonds) > 0:
            last_fetch_time = current_time
            last_bonds_data = bonds
            return bonds[:count]  # Return only the requested number
        return None
    except Exception as e:
        logger.error("Error fetching bonds data: {}".format(e))
        return None

def format_bonds_message(bonds, count=5):
    """
    Format bonds data as a message for Telegram.
    
    Args:
        bonds: List of bond dictionaries
        count: Number of bonds displayed (for title)
    """
    if not bonds or len(bonds) == 0:
        return "Не удалось получить данные по облигациям."
    
    # Format the bonds data as a table for Telegram using HTML formatting
    message = f"<b>🔝 Топ-{count} облигаций с наибольшей доходностью к погашению:</b>\n\n"
    
    # Add each bond as a separate section with emoji indicators
    for i, item in enumerate(bonds, 1):
        # Get values with proper formatting
        isin = item.get('ISIN', "N/A")
        name = item.get('Name', "N/A")
        ytm = "{:.2f}%".format(item.get('Yield to Maturity', 0)) if item.get('Yield to Maturity') is not None else "N/A"
        rating = item.get('Rating', "N/A")
        maturity = item.get('Maturity', "N/A")
        offer_date = item.get('Offer Date', "N/A")
        
        # Create T-Investments link
        tinvest_link = f"https://www.tinkoff.ru/invest/bonds/{isin}/" if isin != "N/A" else "#"
        
        # Add emoji based on position
        position_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        
        # Format the bond information with link
        message += f"{position_emoji} <b>{i}. <a href='{tinvest_link}'>{name}</a></b> ({isin})\n"
        message += f"   📈 Доходность: <b>{ytm}</b>\n"
        message += f"   ⭐️ Рейтинг: {rating}\n"
        message += f"   🗓 Срок погашения: {maturity}\n"
        
        # Add years to offer if available
        if 'Years to Offer Str' in item:
            message += f"   📅 До оферты: {item['Years to Offer Str']}\n"
        
        message += "\n"
    
    message += "<i>Данные с сайта smart-lab.ru</i>"
    
    return message

def handle_command(chat_id, command, user_first_name):
    """Handle bot commands."""
    global subscribed_users
    
    if command == '/start':
        # Handle /start command
        message = "Привет, {}! 👋\n\n".format(user_first_name)
        message += "Я бот, который показывает топ облигаций с наибольшей доходностью к погашению с сайта smart-lab.ru.\n\n"
        message += "Доступные команды:\n"
        message += "/bonds [число] - Получить топ-N облигаций с наибольшей доходностью (по умолчанию 5)\n"
        message += "/subscribe - Подписаться на ежедневные обновления\n"
        message += "/unsubscribe - Отписаться от ежедневных обновлений\n"
        message += "/status - Проверить статус бота\n"
        message += "/help - Показать справку"
        send_message(chat_id, message)
    
    elif command == '/help':
        # Handle /help command
        message = "Доступные команды:\n"
        message += "/start - Начать работу с ботом\n"
        message += "/help - Показать справку\n"
        message += "/bonds [число] - Получить топ-N облигаций с наибольшей доходностью (по умолчанию 5)\n"
        message += "/subscribe - Подписаться на ежедневные обновления\n"
        message += "/unsubscribe - Отписаться от ежедневных обновлений\n"
        message += "/status - Проверить статус бота"
        send_message(chat_id, message)
    
    elif command == '/subscribe':
        # Handle /subscribe command
        subscribed_users.add(chat_id)
        message = "✅ Вы успешно подписались на ежедневные обновления по облигациям!\n\n"
        message += "Вы будете получать информацию о топ облигациях с наибольшей доходностью каждый день в 10:00 МСК."
        send_message(chat_id, message)
    
    elif command == '/unsubscribe':
        # Handle /unsubscribe command
        if chat_id in subscribed_users:
            subscribed_users.remove(chat_id)
            message = "❌ Вы отписались от ежедневных обновлений."
        else:
            message = "Вы не были подписаны на обновления."
        send_message(chat_id, message)
    
    elif command == '/status':
        # Handle /status command
        uptime = int(time.time() - start_time)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        message = "✅ Бот работает исправно\n\n"
        message += "Время работы: {:02d}:{:02d}:{:02d}\n".format(hours, minutes, seconds)
        message += "Количество подписчиков: {}\n".format(len(subscribed_users))
        
        if last_fetch_time:
            last_fetch = datetime.datetime.fromtimestamp(last_fetch_time).strftime('%Y-%m-%d %H:%M:%S')
            message += "Последнее обновление данных: {}".format(last_fetch)
        else:
            message += "Данные еще не загружались"
        
        send_message(chat_id, message)
    
    elif command.startswith('/bonds'):
        # Handle /bonds command with optional count parameter
        # Parse the count parameter if provided (e.g., "/bonds 10")
        parts = command.split()
        count = 5  # Default count
        
        if len(parts) > 1:
            try:
                requested_count = int(parts[1])
                # Limit the count to a reasonable range (1-20)
                count = max(1, min(20, requested_count))
            except ValueError:
                # If conversion fails, use the default count
                pass
        
        send_message(chat_id, f"Получаю данные по топ-{count} облигациям с smart-lab.ru...")
        
        try:
            # Get the bonds with the specified count
            bonds = get_bonds_data(count)
            
            if bonds and len(bonds) > 0:
                # Format the bonds data as a message
                message = format_bonds_message(bonds, count)
                
                # Send the formatted message
                send_message(chat_id, message, parse_mode="HTML")
            else:
                send_message(chat_id, "Не удалось получить данные по облигациям.")
        
        except Exception as e:
            logger.error("Error getting bonds data: {}".format(e))
            send_message(chat_id, "Произошла ошибка при получении данных: {}".format(e))
    
    else:
        # Handle unknown commands
        send_message(
            chat_id,
            "Неизвестная команда. Используйте /help для получения списка доступных команд."
        )

def send_daily_updates():
    """Send daily updates to subscribed users."""
    if not subscribed_users:
        logger.info("No subscribed users to send updates to.")
        return
    
    # Get the bonds data
    bonds = get_bonds_data()
    
    if not bonds or len(bonds) == 0:
        logger.error("Failed to get bonds data for daily updates.")
        return
    
    # Format the message
    message = format_bonds_message(bonds)
    
    # Send to all subscribed users
    for chat_id in subscribed_users:
        try:
            send_message(chat_id, message, parse_mode="HTML")
            logger.info("Sent daily update to chat_id: {}".format(chat_id))
            # Sleep a bit to avoid hitting rate limits
            time.sleep(0.5)
        except Exception as e:
            logger.error("Error sending daily update to chat_id {}: {}".format(chat_id, e))

def is_time_for_daily_update():
    """Check if it's time for the daily update (10:00 MSK)."""
    now = datetime.datetime.now()
    return now.hour == 10 and now.minute == 0

def main():
    """Start the bot."""
    global API_URL
    
    print('Bot is starting...')
    
    # Initialize API URL
    print('Initializing API URL...')
    API_URL = get_api_url()
    print(f'Using API URL: {API_URL}')
    
    # Track the last time we refreshed the API URL
    last_api_refresh = time.time()
    
    # Delete any existing webhook to avoid conflicts
    print('Deleting any existing webhook...')
    delete_webhook()
    
    # Store the ID of the last processed update
    last_update_id = None
    
    # Track the last time we checked for daily updates
    last_daily_check = datetime.datetime.now().replace(microsecond=0)
    
    # Main loop
    while True:
        try:
            # Check if it's time for daily updates
            now = datetime.datetime.now().replace(microsecond=0)
            if now.minute != last_daily_check.minute:  # Check every minute
                if is_time_for_daily_update():
                    logger.info("Sending daily updates...")
                    send_daily_updates()
                last_daily_check = now
            
            # Periodically refresh the API URL (every 10 minutes)
            current_time = time.time()
            if current_time - last_api_refresh > 600:  # 10 minutes
                logger.info("Refreshing API URL...")
                API_URL = get_api_url()
                logger.info(f"Using API URL: {API_URL}")
                last_api_refresh = current_time
            
            # Get updates from Telegram
            updates = get_updates(last_update_id)
            
            if updates and "result" in updates and updates["result"]:
                for update in updates["result"]:
                    # Update the last processed update ID
                    last_update_id = update["update_id"] + 1
                    
                    # Process the message if it exists
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"]
                        user_first_name = update["message"]["from"].get("first_name", "Пользователь")
                        
                        # Handle the command
                        handle_command(chat_id, text, user_first_name)
            
            # Sleep to avoid hitting rate limits
            time.sleep(1)
            
        except KeyboardInterrupt:
            print('Program interrupted')
            break
        except urllib.error.URLError as e:
            # Network-related errors - refresh API URL immediately
            logger.error("Network error in main loop: {}".format(e))
            logger.info("Refreshing API URL due to network error...")
            API_URL = get_api_url()
            logger.info(f"Now using API URL: {API_URL}")
            last_api_refresh = time.time()
            time.sleep(5)  # Wait a bit longer if there's an error
            
        except Exception as e:
            logger.error("Error in main loop: {}".format(e))
            time.sleep(5)  # Wait a bit longer if there's an error

if __name__ == '__main__':
    main()

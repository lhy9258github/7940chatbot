from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import configparser
import logging, datetime, pytz
# import matplotlib.pyplot as plt
# import redis


"""additional packages
In this mini-chatbot, we choose firebase as our database
"""
import firebase_admin
from firebase_admin import db
from firebase_admin import credentials


def main():
	# telegram TOKEN
	config = configparser.ConfigParser()
	config.read("config.ini")
	
	# Update the token info into security way
    # updater = Updater(token=(config['TELEGRAM']['ACCESS_TOKEN']), use_context=True)
	updater = Updater(token=(os.environ.get('TELEGRAM')), use_context=True)
	dispatcher = updater.dispatcher
	# add schedule job package
	j = updater.job_queue
	# the time is UTC, HK_time - 8hours
	job_daily = j.run_daily(refresh_command, days=(0, 1, 2, 3, 4, 5, 6), time=datetime.time(hour=16, minute=2, second=00))
	# initialize the db setting
	init_db()
    # You can set this logging module, so you will know when and why things do not work as expected
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    
    # register a dispatcher to handle message: here we register an echo dispatcher
	echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
	dispatcher.add_handler(echo_handler)

    # on different commands - answer in Telegram
	dispatcher.add_handler(CommandHandler("help", help_command))
	dispatcher.add_handler(CommandHandler("eat", eat_command))
	dispatcher.add_handler(CommandHandler("report", report_command))
	dispatcher.add_handler(CommandHandler("weight", weight_command))

    # To start the bot:
	updater.start_polling()
	updater.idle()


def echo(update, context):
    reply_message = update.message.text.upper()
    # logging.info("Update: " + str(update))
    logging.info("context: " + str(context))
    context.bot.send_message(chat_id=update.effective_chat.id, text= reply_message)

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Helping you helping you.')

def refresh_command(context: CallbackContext) -> None:
	"""Refresh the eat data in mid-night
	"""
	# reset login data
	data = db.reference("login/").get()
	for user in data:
		# upload record data
		curr = db.reference("record/{}".format(user)).get()
		if not curr:
			ret = [data[user]] * 7
		else:
			ret = curr
		ret.pop(0)
		ret.append(data[user])
		path = db.reference("record/")
		new_record =path.update({
			"{}".format(user): ret
		})
		# reset login data
		path = db.reference("login/")
		reU = path.update({
			"{}".format(user): 0.0
		})
	logging.info("refresh successfully.")
	

def eat_command(update: Update, context: CallbackContext) -> None:
	"""Record data when the command /eat is used. 
	"""
	foods = ["rice", "meat", "vegetable"]
	user = update.effective_chat.id
	curr = db.reference("login/{}".format(user)).get()
	if not curr:
		path = db.reference("login/")
		new_user = path.update({
			"{}".format(user): 0.0
		})
		ret = 0.0
	else:
		ret = curr
	logging.info(context.args[0] + ' ' + context.args[1])
	food = context.args[0]
	val = float(context.args[1])
		
	try:
		if food not in foods:
			context.bot.send_message(chat_id=update.effective_chat.id, text='We only support rice, meat and vegetable, please type a correct food.')
		elif food == foods[0]:
			ret += 167 * val
		elif food == foods[1]:
			ret += 287 * val
		elif food == foods[2]:
			ret += 240 * val
		root = db.reference("login/")
		new = root.update({
			"{}".format(user): ret
		})
		# reply total energy until now to target user
		context.bot.send_message(chat_id=update.effective_chat.id, text='Today, you have {} Calories already.'.format(ret))
	except (IndexError, ValueError):
		context.bot.send_message(chat_id=update.effective_chat.id, text='Something wrong, please check.')

def report_command(update: Update, context: CallbackContext) -> None:
	try:
		user = update.effective_chat.id
		curr = db.reference("record/{}".format(user)).get()
		if not curr:
			context.bot.send_message(chat_id=update.effective_chat.id, text="Your record is not in the database, please retry tomorrow")
		else:
			ret = curr
			message = "The average of Calories: " + str(int(sum(ret) / 7))
			# message = ''.join(str(i)+" " for i in ret)
			context.bot.send_message(chat_id=update.effective_chat.id, text=message)
	except (IndexError, ValueError):
		context.bot.send_message(chat_id=update.effective_chat.id, text='Something wrong, please check.')

def weight_command(update: Update, context: CallbackContext) -> None:
	try:
		user = update.effective_chat.id
		wegs = db.reference("weight/{}".format(user)).get()
		path = db.reference("weight/")
		weg_curr = int(context.args[0])
		if not wegs:
			ret = [weg_curr] * 7
			new_user = path.update({
				"{}".format(user): ret
			})
			context.bot.send_message(chat_id=update.effective_chat.id, text='You are the new user, your current weight is {}, you can continue to record your weight value,so we can make an analysis for you.'.format(weg_curr))
		else:
			ret = wegs
			averg_weg = int(sum(ret)/ len(ret))
			message = "The average of your weight is: " + str(averg_weg)
			if averg_weg > weg_curr:
				context.bot.send_message(chat_id=update.effective_chat.id, text=message + ' your weight is lower than average weight, good job!')
			elif averg_weg == weg_curr:
				context.bot.send_message(chat_id=update.effective_chat.id, text=message + ' your weight is equal to average weight, keep doing!')
			elif averg_weg < weg_curr:
				context.bot.send_message(chat_id=update.effective_chat.id, text=message + ' your weight is higher than average weight, be careful!')
			ret.pop(0)
			ret.append(weg_curr)
			new_user = path.update({
				"{}".format(user): ret
			})
	except (IndexError, ValueError):
		context.bot.send_message(chat_id=update.effective_chat.id, text='you must enter the pure number of your weigh with the unit of gram. For example "130".')

def init_db():
	# replace the json file with env
	# cred = credentials.Certificate("mychatbot-e744c-firebase-adminsdk-2j534-cd3d335d16.json")
	cred = credentials.Certificate(os.environ.get('FIREBASE'))
	firebase_admin.initialize_app(cred, {
		'databaseURL': 'https://mychatbot-e744c-default-rtdb.firebaseio.com/'
	})



if __name__ == '__main__':
    main()

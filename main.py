# -*- coding: utf-8 -*-
# @Author: atlekbai
# @Date:   2019-03-16 13:40:30
# @Last Modified by:   atlekbai
# @Last Modified time: 2019-04-08 10:07:01
import logging
import itertools
import json
import sys

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
						ConversationHandler, CallbackQueryHandler, Handler)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

class Node:
	newId = itertools.count()
	def __init__(self, mode, data_name=None, to_show=None):
		self.id = next(Node.newId)
		self.name = None
		self.mode = mode
		self.parents = list()
		self.message = ''
		self.children = list()
		self.options = None
		self.trigger = None
		self.data_name = data_name
		self.to_show = to_show

	def setName(self, name):
		self.name = name

	def addOption(self, option):
		if self.options == None:
			self.options = list()
		self.options.append(option)

	def addParent(self, node):
		self.parents.append(node)

	def addChild(self, node, option=None):
		self.children.append(node)
		node.addParent(self)
		node.trigger = option

	def setOptions(self, options):
		self.options = options

	def setMessage(self, message):
		self.message = message

def findNode(name, nodes):
	for i in range(len(nodes)):
		if nodes[i].name == name:
			return i
	return None

def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def sendMessage(update, message, reply_markup=None):
	query = update.callback_query
	if query:
		query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
	else:
		update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def buildFunc(node):
	modes = {
		'end':ConversationHandler.END
	}

	def func(update, context):
		if 'stack' not in context.user_data:
			context.user_data['stack'] = list()
		reply_markup = None
		query = update.callback_query
		data = None

		prev = context.user_data['stack'][-1] if len(context.user_data['stack']) != 0 else None
		data = query.data if query else update.message.text

		if prev and prev.data_name:
			if prev.data_name not in context.user_data:
				context.user_data[prev.data_name] = list()
			context.user_data[prev.data_name].append(data)

		context.user_data['stack'].append(node)
		if node.mode == 'multi':
			buttons = list()
			for opt in node.options:
				buttons.append(InlineKeyboardButton(opt, callback_data=opt))
			reply_markup = InlineKeyboardMarkup(build_menu(buttons, n_cols=1))

		sendMessage(update, node.message, reply_markup)
		if node.mode == 'end':
			del context.user_data['stack']
			return modes['end']
		if node.mode == 'show':
			message = ''
			for item in node.to_show:
				message += item + '\n'
				for obj in context.user_data[item]:
					message += '- ' + obj + '\n'
			sendMessage(update, message)
		return node.id

	return func

def buildBFS(node, queue):
	queue.append(node)
	for child in node.children:
		queue = buildBFS(child, queue)
	return queue


def buildStates(node):
	filters = {
		'text':Filters.text,
		'show':Filters.text
	}
	handlers = {
		'show':MessageHandler,
		'text':MessageHandler,
		'multi':CallbackQueryHandler
	}

	bfs = buildBFS(node, list())
	bfs.pop(0)
	states = {}
	for elem in bfs:
		for parent in elem.parents:
			if parent.id not in states:
				states[parent.id] = list()
			if parent.mode == 'multi' or parent == 'add':
				states[parent.id].append(handlers[parent.mode](buildFunc(elem), pattern=elem.trigger, pass_user_data=True))
			else:
				states[parent.id].append(handlers[parent.mode](filters[parent.mode], buildFunc(elem), pass_user_data=True))
	return states

'''
tag:
	0 - answer
	1 - multi
	2 - multi
	3 - text
	4 - show
	5 - end
'''
def main():
	f = open(sys.argv[1], "r")
	data = f.read()
	f.close()
	data = json.loads(data)
	nodes = list()
	for obj in data['nodes']:
		tmp = data['nodes'][obj]
		if 'data' in tmp:
			node = Node(tmp['mode'], tmp['data'])
		elif 'show' in tmp:
			node = Node(tmp['mode'], to_show=tmp['show'])
		else:
			node = Node(tmp['mode'])
		
		node.setMessage(tmp['message'])
		if 'options' in tmp:
			node.setOptions(tmp['options'])
		node.setName(obj)
		nodes.append(node)

	for node1 in data['connections']:
		for node2 in data['connections'][node1]:
			option = None
			idx1 = findNode(node1, nodes)
			idx2 = findNode(node2['node'], nodes)

			if 'option' in node2:
				option = node2['option']
			nodes[idx1].addChild(nodes[idx2], option)

	updater = Updater("TOKEN", use_context=True)

	conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', buildFunc(nodes[0]), pass_user_data=True)],
        states = buildStates(nodes[0]),
        fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True)]
    )
	dp = updater.dispatcher
	dp.add_handler(conv_handler)
	dp.add_error_handler(error)
	updater.start_polling()
	updater.idle()


if __name__ == '__main__':
    main()
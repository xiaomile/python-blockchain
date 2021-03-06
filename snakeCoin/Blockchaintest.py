import hashlib
import json
import requests
from textwrap import dedent

from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask,jsonify,request

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        # Create the genesis block
        self.new_block(previous_hash=1,proof=100)
        self.nodes = set()

    def register_node(self,address):
        #add a new node to the list of nodes
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self,proof,previous_hash=None):
        # Creates a new Block and adds it to chain
        block = {
            'index':len(self.chain)+1,
            'timestamp':time(),
            'transactions':self.current_transactions,
            'proof':proof,
            'previous_hash':previous_hash or self.hash(self.chain[-1]),
        }
        #reset the current list of transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self,sender,recipient,amount):
        # Adds a new transaction to the list of transactions
        #生成新交易信息,信息将加入到下一个待挖的区块中
        self.current_transactions.append({
            'sender':sender,
            'recipient':recipient,
            'amount':amount,
        })
        return self.last_block['index']+1

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        共识算法解决冲突
        使用网络中最长的链.
        :return: <bool> True 如果链被取代, 否则为False
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    @property
    def last_block(self):
        # Hashes a Block
        return self.chain[-1]

    @staticmethod
    def hash(block):
        # Returns the last Block in the chain
        #生成块的SHA-256 hash值
        block_string = json.dumps(block,sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self,last_proof):
        #查找一个字符串，使其与上一个字符串的hash以4个0开头
        proof = 0
        while self.valid_proof(last_proof,proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof,proof):
        #验证hash
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'

app = Flask(__name__,static_url_path='')
node_identifier = str(uuid4()).replace('-','')
blockchain = Blockchain()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/mine',methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender="0",
        recipient = node_identifier,
        amount = 1,
    )
    block = blockchain.new_block(proof)
    response = {
        'message':"New Block Forged",
        'index':block['index'],
        'transactions':block['transactions'],
        'proof':block['proof'],
        'previous_hash':block['previous_hash'],
    }
    return jsonify(response),200

@app.route('/chain',methods=['GET'])
def full_chain():
    response = {
        'chain':blockchain.chain,
        'length':len(blockchain.chain),
    }
    return jsonify(response),200

@app.route('/transactions/new',methods=['POST'])
def new_transactions():
    print(request.data)
    print(request.get_json())
    #values = request.get_data().replace(b'\r\n',b'')
    values = request.get_json()
    #values = str(values)
    required = ['sender','recipient','amount']
    if not all(k in values for k in required):
        return 'Missing values',400

    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response = {'message':f'Transactions will be added to Block {index}'}
    return jsonify(response),201
    
    #return "We'll add a new transaction"

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    print(request.data)
    values = request.get_json()
    print(request)
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000)

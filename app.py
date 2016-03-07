from flask import Flask, abort, jsonify, request, send_file
from flask.ext.pymongo import PyMongo

app = Flask(__name__)
mongo = PyMongo(app)

ALLOWED_TASK_STATES = ['todo', 'doing', 'done', 'deleted']


def sanitize_task_or_400(task_entry):

    title = task_entry.get('title') or abort(400)
    state = task_entry.get('state') or abort(400)
    price = task_entry.get('price') or abort(400)

    if state not in ALLOWED_TASK_STATES:
        abort(400)

    try:
        price = float(price)
    except ValueError:
        abort(400)

    return {'title': title.strip(), 'state': state, 'price': round(price, 2)}


def before_jsonify_task(task):
    return {
        'title': task['title'],
        'state': task['state'],
        'price': task['price'],
        'id': str(task['_id']),
        'created': int(task['_id'].generation_time.strftime('%s'))
    }


def get_totals():
    cursor = mongo.db.tasks.aggregate([
        {'$match': {'state': {'$ne': 'deleted'}}},
        {"$group": {"_id": "$state", "count": {"$sum": "$price"}}}])
    return dict((i['_id'], i['count']) for i in cursor)


@app.route('/', methods=['GET'])
def index():
    return send_file('index.html')


@app.route('/create_task', methods=['POST'])
def create_task():
    task_entry = sanitize_task_or_400(dict(request.form.to_dict(), state='todo'))
    mongo.db.tasks.insert_one(task_entry)
    return jsonify(
        task=before_jsonify_task(task_entry),
        totals=get_totals())


@app.route('/update_task/<ObjectId:task_id>', methods=['POST'])
def update_task(task_id):
    task_entry = mongo.db.tasks.find_one_or_404(task_id)
    if not set(request.form) & {'title', 'state'}:
        abort(400)
    updated_task = sanitize_task_or_400(dict(
        title=request.form.get('title') or task_entry['title'],
        state=request.form.get('state') or task_entry['state'],
        price=task_entry['price']))
    mongo.db.tasks.update({'_id': task_id}, updated_task)
    return jsonify(
        task=before_jsonify_task(dict(updated_task, _id=task_id)),
        totals=get_totals() if 'state' in request.form else None)


@app.route('/list_tasks', methods=['GET'])
def list_tasks():
        default_requested_states = set(ALLOWED_TASK_STATES) - {'deleted'}
        requested_states = request.args.getlist('state') or default_requested_states
        query_states = set(requested_states) & set(ALLOWED_TASK_STATES)
        tasks = mongo.db.tasks.find({'state': {'$in': tuple(query_states)}})
        return jsonify(
            tasks=[before_jsonify_task(t) for t in tasks],
            totals=get_totals())

if __name__ == '__main__':
    app.run(debug=True)

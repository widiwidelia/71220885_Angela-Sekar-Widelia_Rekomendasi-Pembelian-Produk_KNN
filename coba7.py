import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
import json
import sys
import datetime

def load_data_and_train_model():
    file_name = 'dataset.csv'
    column_title = ['userID', 'productID', 'rating', 'timestamp']
    ds = pd.read_csv(file_name, names=column_title, header=None)
    ds = ds.dropna()
    ds['date'] = pd.to_datetime(ds['timestamp'], unit='s')

    ds['userID'] = ds['userID'].astype('category').cat.codes
    ds['productID'] = ds['productID'].astype('category').cat.codes

    user_mapping = {user: index for index, user in enumerate(ds['userID'].astype(str).unique())}
    product_mapping = {product: index for index, product in enumerate(ds['productID'].astype(str).unique())}
    user_inverse_mapper = {index: user for user, index in user_mapping.items()}
    product_inverse_mapper = {index: product for product, index in product_mapping.items()}

    user_index = ds['userID']
    product_index = ds['productID']
    sparse_matrix = csr_matrix((ds['rating'], (user_index, product_index)), shape=(len(user_mapping), len(product_mapping)))

    data_train = ds
    train_user_index = data_train['userID']
    train_product_index = data_train['productID']
    train_sparse_matrix = csr_matrix((data_train['rating'], (train_user_index, train_product_index)), shape=(len(user_mapping), len(product_mapping)))

    knn = NearestNeighbors(metric='cosine', algorithm='brute')
    knn.fit(train_sparse_matrix.T)

    return knn, train_sparse_matrix, user_mapping, product_mapping, user_inverse_mapper, product_inverse_mapper, ds

def recommend_products(user_id, sparse_matrix, user_mapping, product_inverse_mapper, knn, ds, n_recommendations=8, time_threshold=pd.Timestamp.now() - pd.Timedelta(days=365)):
    user_idx = user_mapping[int(user_id)]
    user_ratings = sparse_matrix[user_idx, :].toarray().flatten()
    rated_items = np.where(user_ratings > 0)[0]
    
    recommendations = {}
    
    for item_idx in rated_items:
        distances, indices = knn.kneighbors(sparse_matrix.T[item_idx], n_neighbors=n_recommendations+1)
        similar_items = indices.flatten()[1:]
        similar_items_scores = distances.flatten()[1:]
        
        user_item_timestamp = ds[(ds['userID'] == user_idx) & (ds['productID'] == item_idx)]['date'].values[0]
        
        for similar_item_idx, score in zip(similar_items, similar_items_scores):
            similar_item = product_inverse_mapper[similar_item_idx]
            if similar_item not in recommendations:
                recommendations[similar_item] = [score, user_item_timestamp]
            else:
                recommendations[similar_item][0] += score
                recommendations[similar_item][1] = min(recommendations[similar_item][1], user_item_timestamp)
    
    recommendations = sorted(recommendations.items(), key=lambda x: (x[1][0], -pd.Timestamp(x[1][1]).timestamp()), reverse=True)
    
    recommendations = recommendations[:n_recommendations]
    filtered_recommendations = [item for item in recommendations if item[1][1] > time_threshold]
    
    if not filtered_recommendations:
        filtered_recommendations = recommendations
    
    avg_ratings = {item[0]: ds[ds['productID'] == item[0]]['rating'].mean() for item in filtered_recommendations}
    
    return [(item[0], avg_ratings[item[0]]) for item in filtered_recommendations]

if __name__ == '__main__':
    user_id = sys.argv[1]
    knn, sparse_matrix, user_mapping, product_mapping, user_inverse_mapper, product_inverse_mapper, ds = load_data_and_train_model()
    recommendations = recommend_products(user_id, sparse_matrix, user_mapping, product_inverse_mapper, knn, ds)
    output = json.dumps(recommendations)
    print(output)

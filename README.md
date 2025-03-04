# RecommenderModel
We built a recommender system model that uses the power of boosting and NLP applications to predict user's ratings on items. We built a boosting model that models the matrix of ratings and unstructured text in successive stages.
The first stage is a collaborative filtering model using the matrix of ratings while the second stage is a multinomial model using text information to model the residuals from the first stage. These two stages combined together in an ensemble is used as a base estimator for our model. 
More specifically, the ensemble model consist of two classifiers :

• Collaborative filtering recommender that incorporates temporal effects as in Koren and Bell (2011) with a little change where rating are considered a class of 5 categories (1through 5). We use some of the implementation of https://github.com/rudolfsteiner/CollaborativeFilteringV3.git with appropriate modifications.

• A 5-class multinomial model that incorporates features derived from user feedback by leveraging BERT. BERT, a pre-trained model, transforms written item reviews into numeric vectors, capturing contextual information about user experiences. These vectors, combined with user-provided ratings, are used as features to enhance the model’s predictive capabilities. In this case we used ’bert-base-uncased’ with 12 layers.

In summary  our model is a recommender system that applies Logistboost and sequentially uses the two-stage ensemble model as its base estimator.

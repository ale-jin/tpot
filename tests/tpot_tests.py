# -*- coding: utf-8 -*-

"""Copyright 2015-Present Randal S. Olson.

This file is part of the TPOT library.

TPOT is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

TPOT is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with TPOT. If not, see <http://www.gnu.org/licenses/>.

"""

from tpot import TPOTClassifier, TPOTRegressor
from tpot.base import TPOTBase
from tpot.export_utils import get_by_name
from tpot.gp_types import Output_Array
from tpot.gp_deap import mutNodeReplacement
from tpot.metrics import balanced_accuracy
from tpot.built_in_operators import StackingEstimator, ZeroCount
from tpot.operator_utils import TPOTOperatorClassFactory, set_sample_weight
from tpot.config_classifier import classifier_config_dict
from tpot.config_classifier_light import classifier_config_dict_light
from tpot.config_regressor_light import regressor_config_dict_light
from tpot.config_classifier_mdr import tpot_mdr_classifier_config_dict
from tpot.config_regressor_mdr import tpot_mdr_regressor_config_dict
from tpot.config_classifier_sparse import classifier_config_sparse
from tpot.config_regressor_sparse import regressor_config_sparse
from tpot.driver import float_range

import numpy as np
import inspect
import random

from sklearn.datasets import load_digits, load_boston
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression, Lasso
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.pipeline import make_pipeline
from deap import creator
from nose.tools import assert_raises, assert_not_equal

from tqdm import tqdm

# Set up the MNIST data set for testing
mnist_data = load_digits()
training_features, testing_features, training_classes, testing_classes = \
    train_test_split(mnist_data.data.astype(np.float64), mnist_data.target.astype(np.float64), random_state=42)

# Set up the Boston data set for testing
boston_data = load_boston()
training_features_r, testing_features_r, training_classes_r, testing_classes_r = \
    train_test_split(boston_data.data, boston_data.target, random_state=42)

np.random.seed(42)
random.seed(42)

test_operator_key = 'sklearn.feature_selection.SelectPercentile'
TPOTSelectPercentile, TPOTSelectPercentile_args = TPOTOperatorClassFactory(
    test_operator_key,
    classifier_config_dict[test_operator_key]
)


def test_init_custom_parameters():
    """Assert that the TPOT instantiator stores the TPOT variables properly."""
    tpot_obj = TPOTClassifier(
        population_size=500,
        generations=1000,
        offspring_size=2000,
        mutation_rate=0.05,
        crossover_rate=0.9,
        scoring='accuracy',
        cv=10,
        verbosity=1,
        random_state=42,
        disable_update_check=True,
        warm_start=True
    )

    assert tpot_obj.population_size == 500
    assert tpot_obj.generations == 1000
    assert tpot_obj.offspring_size == 2000
    assert tpot_obj.mutation_rate == 0.05
    assert tpot_obj.crossover_rate == 0.9
    assert tpot_obj.scoring_function == 'accuracy'
    assert tpot_obj.cv == 10
    assert tpot_obj.max_time_mins is None
    assert tpot_obj.warm_start is True
    assert tpot_obj.verbosity == 1
    assert tpot_obj._optimized_pipeline is None
    assert tpot_obj._fitted_pipeline is None
    assert not (tpot_obj._pset is None)
    assert not (tpot_obj._toolbox is None)


def test_init_default_scoring():
    """Assert that TPOT intitializes with the correct default scoring function."""
    tpot_obj = TPOTRegressor()
    assert tpot_obj.scoring_function == 'neg_mean_squared_error'

    tpot_obj = TPOTClassifier()
    assert tpot_obj.scoring_function == 'accuracy'


def test_invaild_score_warning():
    """Assert that the TPOT intitializes raises a ValueError when the scoring metrics is not available in SCORERS."""
    # Mis-spelled scorer
    assert_raises(ValueError, TPOTClassifier, scoring='balanced_accuray')
    # Correctly spelled
    TPOTClassifier(scoring='balanced_accuracy')


def test_invaild_dataset_warning():
    """Assert that the TPOT fit function raises a ValueError when dataset is not in right format."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0
    )
    # common mistake in classes
    bad_training_classes = training_classes.reshape((1, len(training_classes)))
    assert_raises(ValueError, tpot_obj.fit, training_features, bad_training_classes)


def test_invaild_subsample_ratio_warning():
    """Assert that the TPOT intitializes raises a ValueError when subsample ratio is not in the range (0.0, 1.0]."""
    # Invalid ratio
    assert_raises(ValueError, TPOTClassifier, subsample=0.0)
    # Valid ratio
    TPOTClassifier(subsample=0.1)


def test_init_max_time_mins():
    """Assert that the TPOT init stores max run time and sets generations to 1000000."""
    tpot_obj = TPOTClassifier(max_time_mins=30, generations=1000)

    assert tpot_obj.generations == 1000000
    assert tpot_obj.max_time_mins == 30


def test_balanced_accuracy():
    """Assert that the balanced_accuracy in TPOT returns correct accuracy."""
    y_true = np.array([1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4])
    y_pred1 = np.array([1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4])
    y_pred2 = np.array([3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4])
    accuracy_score1 = balanced_accuracy(y_true, y_pred1)
    accuracy_score2 = balanced_accuracy(y_true, y_pred2)
    assert np.allclose(accuracy_score1, 1.0)
    assert np.allclose(accuracy_score2, 0.833333333333333)


def test_get_params():
    """Assert that get_params returns the exact dictionary of parameters used by TPOT."""
    kwargs = {
        'population_size': 500,
        'generations': 1000,
        'config_dict': 'TPOT light',
        'offspring_size': 2000,
        'verbosity': 1
    }

    tpot_obj = TPOTClassifier(**kwargs)
    # Get default parameters of TPOT and merge with our specified parameters
    initializer = inspect.getargspec(TPOTBase.__init__)
    default_kwargs = dict(zip(initializer.args[1:], initializer.defaults))
    default_kwargs.update(kwargs)
    # update to dictionary instead of input string
    default_kwargs.update({'config_dict': classifier_config_dict_light})
    assert tpot_obj.get_params()['config_dict'] == default_kwargs['config_dict']
    assert tpot_obj.get_params() == default_kwargs


def test_set_params():
    """Assert that set_params returns a reference to the TPOT instance."""
    tpot_obj = TPOTClassifier()
    assert tpot_obj.set_params() is tpot_obj


def test_set_params_2():
    """Assert that set_params updates TPOT's instance variables."""
    tpot_obj = TPOTClassifier(generations=2)
    tpot_obj.set_params(generations=3)

    assert tpot_obj.generations == 3


def test_conf_dict():
    """Assert that TPOT uses the pre-configured dictionary of operators when config_dict is 'TPOT light' or 'TPOT MDR'."""
    tpot_obj = TPOTClassifier(config_dict='TPOT light')
    assert tpot_obj.config_dict == classifier_config_dict_light

    tpot_obj = TPOTClassifier(config_dict='TPOT MDR')
    assert tpot_obj.config_dict == tpot_mdr_classifier_config_dict

    tpot_obj = TPOTClassifier(config_dict='TPOT sparse')
    assert tpot_obj.config_dict == classifier_config_sparse

    tpot_obj = TPOTRegressor(config_dict='TPOT light')
    assert tpot_obj.config_dict == regressor_config_dict_light

    tpot_obj = TPOTRegressor(config_dict='TPOT MDR')
    assert tpot_obj.config_dict == tpot_mdr_regressor_config_dict

    tpot_obj = TPOTRegressor(config_dict='TPOT sparse')
    assert tpot_obj.config_dict == regressor_config_sparse


def test_conf_dict_2():
    """Assert that TPOT uses a custom dictionary of operators when config_dict is Python dictionary."""
    tpot_obj = TPOTClassifier(config_dict=tpot_mdr_classifier_config_dict)
    assert tpot_obj.config_dict == tpot_mdr_classifier_config_dict


def test_conf_dict_3():
    """Assert that TPOT uses a custom dictionary of operators when config_dict is the path of Python dictionary."""
    tpot_obj = TPOTRegressor(config_dict='tests/test_config.py')
    tested_config_dict = {
        'sklearn.naive_bayes.GaussianNB': {
        },

        'sklearn.naive_bayes.BernoulliNB': {
            'alpha': [1e-3, 1e-2, 1e-1, 1., 10., 100.],
            'fit_prior': [True, False]
        },

        'sklearn.naive_bayes.MultinomialNB': {
            'alpha': [1e-3, 1e-2, 1e-1, 1., 10., 100.],
            'fit_prior': [True, False]
        }
    }
    assert isinstance(tpot_obj.config_dict, dict)
    assert tpot_obj.config_dict == tested_config_dict


def test_random_ind():
    """Assert that the TPOTClassifier can generate the same pipeline with same random seed."""
    tpot_obj = TPOTClassifier(random_state=43)
    pipeline1 = str(tpot_obj._toolbox.individual())
    tpot_obj = TPOTClassifier(random_state=43)
    pipeline2 = str(tpot_obj._toolbox.individual())
    assert pipeline1 == pipeline2


def test_score():
    """Assert that the TPOT score function raises a RuntimeError when no optimized pipeline exists."""
    tpot_obj = TPOTClassifier()
    assert_raises(RuntimeError, tpot_obj.score, testing_features, testing_classes)


def test_score_2():
    """Assert that the TPOTClassifier score function outputs a known score for a fixed pipeline."""
    tpot_obj = TPOTClassifier(random_state=34)
    known_score = 0.977777777778  # Assumes use of the TPOT accuracy function

    # Create a pipeline with a known score
    pipeline_string = (
        'KNeighborsClassifier('
        'input_matrix, '
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1, '
        'KNeighborsClassifier__weights=uniform'
        ')'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)
    # Get score from TPOT
    score = tpot_obj.score(testing_features, testing_classes)

    assert np.allclose(known_score, score)


def test_score_3():
    """Assert that the TPOTRegressor score function outputs a known score for a fixed pipeline."""
    tpot_obj = TPOTRegressor(scoring='neg_mean_squared_error', random_state=72)
    known_score = 12.1791953611

    # Reify pipeline with known score
    pipeline_string = (
        "ExtraTreesRegressor("
        "GradientBoostingRegressor(input_matrix, GradientBoostingRegressor__alpha=0.8,"
        "GradientBoostingRegressor__learning_rate=0.1,GradientBoostingRegressor__loss=huber,"
        "GradientBoostingRegressor__max_depth=5, GradientBoostingRegressor__max_features=0.5,"
        "GradientBoostingRegressor__min_samples_leaf=5, GradientBoostingRegressor__min_samples_split=5,"
        "GradientBoostingRegressor__n_estimators=100, GradientBoostingRegressor__subsample=0.25),"
        "ExtraTreesRegressor__bootstrap=True, ExtraTreesRegressor__max_features=0.5,"
        "ExtraTreesRegressor__min_samples_leaf=5, ExtraTreesRegressor__min_samples_split=5, "
        "ExtraTreesRegressor__n_estimators=100)"
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r)

    # Get score from TPOT
    score = tpot_obj.score(testing_features_r, testing_classes_r)

    assert np.allclose(known_score, score)


def test_sample_weight_func():
    """Assert that the TPOTRegressor score function outputs a known score for a fixed pipeline with sample weights."""
    tpot_obj = TPOTRegressor(scoring='neg_mean_squared_error')

    # Reify pipeline with known scor
    pipeline_string = (
        "ExtraTreesRegressor("
        "GradientBoostingRegressor(input_matrix, GradientBoostingRegressor__alpha=0.8,"
        "GradientBoostingRegressor__learning_rate=0.1,GradientBoostingRegressor__loss=huber,"
        "GradientBoostingRegressor__max_depth=5, GradientBoostingRegressor__max_features=0.5,"
        "GradientBoostingRegressor__min_samples_leaf=5, GradientBoostingRegressor__min_samples_split=5,"
        "GradientBoostingRegressor__n_estimators=100, GradientBoostingRegressor__subsample=0.25),"
        "ExtraTreesRegressor__bootstrap=True, ExtraTreesRegressor__max_features=0.5,"
        "ExtraTreesRegressor__min_samples_leaf=5, ExtraTreesRegressor__min_samples_split=5, "
        "ExtraTreesRegressor__n_estimators=100)"
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r)

    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)

    # make up a sample weight
    training_classes_r_weight = np.array(range(1, len(training_classes_r)+1))
    training_classes_r_weight_dict = set_sample_weight(tpot_obj._fitted_pipeline.steps, training_classes_r_weight)

    np.random.seed(42)
    cv_score1 = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error')

    np.random.seed(42)
    cv_score2 = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error')

    np.random.seed(42)
    cv_score_weight = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error', fit_params=training_classes_r_weight_dict)

    np.random.seed(42)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r, **training_classes_r_weight_dict)
    # Get score from TPOT
    known_score = 11.5790430757
    score = tpot_obj.score(testing_features_r, testing_classes_r)

    assert np.allclose(cv_score1, cv_score2)
    assert not np.allclose(cv_score1, cv_score_weight)
    assert np.allclose(known_score, score)


def test_predict():
    """Assert that the TPOT predict function raises a RuntimeError when no optimized pipeline exists."""
    tpot_obj = TPOTClassifier()
    assert_raises(RuntimeError, tpot_obj.predict, testing_features)


def test_predict_2():
    """Assert that the TPOT predict function returns a numpy matrix of shape (num_testing_rows,)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5'
        ')'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)
    result = tpot_obj.predict(testing_features)

    assert result.shape == (testing_features.shape[0],)


def test_predict_proba():
    """Assert that the TPOT predict_proba function returns a numpy matrix of shape (num_testing_rows, num_testing_classes)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5)'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)

    result = tpot_obj.predict_proba(testing_features)
    num_labels = np.amax(testing_classes) + 1

    assert result.shape == (testing_features.shape[0], num_labels)


def test_predict_proba2():
    """Assert that the TPOT predict_proba function returns a numpy matrix filled with probabilities (float)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5)'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)

    result = tpot_obj.predict_proba(testing_features)
    rows, columns = result.shape

    for i in range(rows):
        for j in range(columns):
            float_range(result[i][j])


def test_warm_start():
    """Assert that the TPOT warm_start flag stores the pop and pareto_front from the first run."""
    tpot_obj = TPOTClassifier(random_state=42, population_size=1, offspring_size=2, generations=1, verbosity=0, warm_start=True)
    tpot_obj.fit(training_features, training_classes)

    assert tpot_obj._pop is not None
    assert tpot_obj._pareto_front is not None

    first_pop = tpot_obj._pop
    tpot_obj.random_state = 21
    tpot_obj.fit(training_features, training_classes)

    assert tpot_obj._pop == first_pop


def test_fit():
    """Assert that the TPOT fit function provides an optimized pipeline."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0
    )
    tpot_obj.fit(training_features, training_classes)

    assert isinstance(tpot_obj._optimized_pipeline, creator.Individual)
    assert not (tpot_obj._start_datetime is None)


def test_fit2():
    """Assert that the TPOT fit function provides an optimized pipeline when config_dict is 'TPOT light'."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    tpot_obj.fit(training_features, training_classes)

    assert isinstance(tpot_obj._optimized_pipeline, creator.Individual)
    assert not (tpot_obj._start_datetime is None)


def test_fit3():
    """Assert that the TPOT fit function provides an optimized pipeline with subsample is 0.8"""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        subsample=0.8,
        verbosity=0
    )
    tpot_obj.fit(training_features, training_classes)

    assert isinstance(tpot_obj._optimized_pipeline, creator.Individual)
    assert not (tpot_obj._start_datetime is None)


def test_evaluated_individuals():
    """Assert that _evaluated_individuals stores corrent pipelines and their CV scores."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=2,
        offspring_size=4,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    tpot_obj.fit(training_features, training_classes)
    assert isinstance(tpot_obj._evaluated_individuals, dict)
    for pipeline_string in sorted(tpot_obj._evaluated_individuals.keys()):
        deap_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
        sklearn_pipeline = tpot_obj._toolbox.compile(expr=deap_pipeline)
        tpot_obj._set_param_recursive(sklearn_pipeline.steps, 'random_state', 42)
        operator_count = tpot_obj._operator_count(deap_pipeline)

        try:
            cv_scores = cross_val_score(sklearn_pipeline, training_features, training_classes, cv=5, scoring='accuracy', verbose=0)
            mean_cv_scores = np.mean(cv_scores)
        except Exception as e:
            mean_cv_scores = -float('inf')

        assert np.allclose(tpot_obj._evaluated_individuals[pipeline_string][1], mean_cv_scores)
        assert np.allclose(tpot_obj._evaluated_individuals[pipeline_string][0], operator_count)


def test_evaluate_individuals():
    """Assert that _evaluate_individuals returns operator_counts and CV scores in correct order."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        verbosity=0,
        config_dict='TPOT light'
    )

    tpot_obj._pbar = tqdm(total=1, disable=True)
    pop = tpot_obj._toolbox.population(n=10)
    fitness_scores = tpot_obj._evaluate_individuals(pop, training_features, training_classes)

    for deap_pipeline, fitness_score in zip(pop, fitness_scores):
        operator_count = tpot_obj._operator_count(deap_pipeline)
        sklearn_pipeline = tpot_obj._toolbox.compile(expr=deap_pipeline)
        tpot_obj._set_param_recursive(sklearn_pipeline.steps, 'random_state', 42)

        try:
            cv_scores = cross_val_score(sklearn_pipeline, training_features, training_classes, cv=5, scoring='accuracy', verbose=0)
            mean_cv_scores = np.mean(cv_scores)
        except Exception as e:
            mean_cv_scores = -float('inf')

        assert isinstance(deap_pipeline, creator.Individual)
        assert np.allclose(fitness_score[0], operator_count)
        assert np.allclose(fitness_score[1], mean_cv_scores)


def test_imputer():
    """Assert that the TPOT fit function will not raise a ValueError in a dataset where NaNs are present."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    features_with_nan = np.copy(training_features)
    features_with_nan[0][0] = float('nan')

    tpot_obj.fit(features_with_nan, training_classes)


def test_imputer2():
    """Assert that the TPOT predict function will not raise a ValueError in a dataset where NaNs are present."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    features_with_nan = np.copy(training_features)
    features_with_nan[0][0] = float('nan')

    tpot_obj.fit(features_with_nan, training_classes)
    tpot_obj.predict(features_with_nan)


def test_imputer3():
    """Assert that the TPOT _impute_values function returns a feature matrix with imputed NaN values."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    features_with_nan = np.copy(training_features)
    features_with_nan[0][0] = float('nan')

    imputed_features = tpot_obj._impute_values(features_with_nan)
    assert_not_equal(imputed_features[0][0], float('nan'))


def test_tpot_operator_factory_class():
    """Assert that the TPOT operators class factory."""
    test_config_dict = {
        'sklearn.svm.LinearSVC': {
            'penalty': ["l1", "l2"],
            'loss': ["hinge", "squared_hinge"],
            'dual': [True, False],
            'tol': [1e-5, 1e-4, 1e-3, 1e-2, 1e-1],
            'C': [1e-4, 1e-3, 1e-2, 1e-1, 0.5, 1., 5., 10., 15., 20., 25.]
        },

        'sklearn.linear_model.LogisticRegression': {
            'penalty': ["l1", "l2"],
            'C': [1e-4, 1e-3, 1e-2, 1e-1, 0.5, 1., 5., 10., 15., 20., 25.],
            'dual': [True, False]
        },

        'sklearn.preprocessing.Binarizer': {
            'threshold': np.arange(0.0, 1.01, 0.05)
        }
    }

    tpot_operator_list = []
    tpot_argument_list = []

    for key in sorted(test_config_dict.keys()):
        op, args = TPOTOperatorClassFactory(key, test_config_dict[key])
        tpot_operator_list.append(op)
        tpot_argument_list += args

    assert len(tpot_operator_list) == 3
    assert len(tpot_argument_list) == 9
    assert tpot_operator_list[0].root is True
    assert tpot_operator_list[1].root is False
    assert tpot_operator_list[2].type() == "Classifier or Regressor"
    assert tpot_argument_list[1].values == [True, False]


def test_mutNodeReplacement():
    """Assert that mutNodeReplacement() returns the correct type of mutation node in a fixed pipeline."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'KNeighborsClassifier(CombineDFs('
        'DecisionTreeClassifier(input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5'
        '), '
        'SelectPercentile('
        'input_matrix, '
        'SelectPercentile__percentile=20'
        ')'
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1, '
        'KNeighborsClassifier__weights=uniform'
        ')'
    )

    pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    pipeline[0].ret = Output_Array
    old_ret_type_list = [node.ret for node in pipeline]
    old_prims_list = [node for node in pipeline if node.arity != 0]
    mut_ind = mutNodeReplacement(pipeline, pset=tpot_obj._pset)
    new_ret_type_list = [node.ret for node in mut_ind[0]]
    new_prims_list = [node for node in mut_ind[0] if node.arity != 0]

    if new_prims_list == old_prims_list:  # Terminal mutated
        assert new_ret_type_list == old_ret_type_list
    else:  # Primitive mutated
        diff_prims = list(set(new_prims_list).symmetric_difference(old_prims_list))
        assert diff_prims[0].ret == diff_prims[1].ret

    assert mut_ind[0][0].ret == Output_Array


def test_operator_type():
    """Assert that TPOT operators return their type, e.g. 'Classifier', 'Preprocessor'."""
    assert TPOTSelectPercentile.type() == "Preprocessor or Selector"


def test_get_by_name():
    """Assert that the Operator class returns operators by name appropriately."""
    tpot_obj = TPOTClassifier()
    assert get_by_name("SelectPercentile", tpot_obj.operators).__class__ == TPOTSelectPercentile.__class__


def test_gen():
    """Assert that TPOT's gen_grow_safe function returns a pipeline of expected structure."""
    tpot_obj = TPOTClassifier()

    pipeline = tpot_obj._gen_grow_safe(tpot_obj._pset, 1, 3)

    assert len(pipeline) > 1
    assert pipeline[0].ret == Output_Array


def test_StackingEstimator_1():
    """Assert that the StackingEstimator returns transformed X with synthetic features in classification."""
    clf = RandomForestClassifier(random_state=42)
    stack_clf = StackingEstimator(estimator=RandomForestClassifier(random_state=42))
    # fit
    clf.fit(training_features, training_classes)
    stack_clf.fit(training_features, training_classes)
    # get transformd X
    X_clf_transformed = stack_clf.transform(training_features)

    assert np.allclose(clf.predict(training_features), X_clf_transformed[:, 0])
    assert np.allclose(clf.predict_proba(training_features), X_clf_transformed[:, 1:1 + len(np.unique(training_classes))])


def test_StackingEstimator_2():
    """Assert that the StackingEstimator returns transformed X with a synthetic feature in regression."""
    reg = RandomForestRegressor(random_state=42)
    stack_reg = StackingEstimator(estimator=RandomForestRegressor(random_state=42))
    # fit
    reg.fit(training_features_r, training_classes_r)
    stack_reg.fit(training_features_r, training_classes_r)
    # get transformd X
    X_reg_transformed = stack_reg.transform(training_features_r)

    assert np.allclose(reg.predict(training_features_r), X_reg_transformed[:, 0])


def test_StackingEstimator_3():
    """Assert that the StackingEstimator worked as expected in scikit-learn pipeline in classification"""
    stack_clf = StackingEstimator(estimator=RandomForestClassifier(random_state=42))
    meta_clf = LogisticRegression()
    sklearn_pipeline = make_pipeline(stack_clf, meta_clf)
    # fit in pipeline
    sklearn_pipeline.fit(training_features, training_classes)
    # fit step by step
    stack_clf.fit(training_features, training_classes)
    X_clf_transformed = stack_clf.transform(training_features)
    meta_clf.fit(X_clf_transformed, training_classes)
    # scoring
    score = meta_clf.score(X_clf_transformed, training_classes)
    pipeline_score = sklearn_pipeline.score(training_features, training_classes)
    assert np.allclose(score, pipeline_score)

    # test cv score
    cv_score = np.mean(cross_val_score(sklearn_pipeline, training_features, training_classes, cv=3, scoring='accuracy'))

    known_cv_score = 0.947282375315

    assert np.allclose(known_cv_score, cv_score)


def test_StackingEstimator_4():
    """Assert that the StackingEstimator worked as expected in scikit-learn pipeline in regression"""
    stack_reg = StackingEstimator(estimator=RandomForestRegressor(random_state=42))
    meta_reg = Lasso(random_state=42)
    sklearn_pipeline = make_pipeline(stack_reg, meta_reg)
    # fit in pipeline
    sklearn_pipeline.fit(training_features_r, training_classes_r)
    # fit step by step
    stack_reg.fit(training_features_r, training_classes_r)
    X_reg_transformed = stack_reg.transform(training_features_r)
    meta_reg.fit(X_reg_transformed, training_classes_r)
    # scoring
    score = meta_reg.score(X_reg_transformed, training_classes_r)
    pipeline_score = sklearn_pipeline.score(training_features_r, training_classes_r)
    assert np.allclose(score, pipeline_score)

    # test cv score
    cv_score = np.mean(cross_val_score(sklearn_pipeline, training_features_r, training_classes_r, cv=3, scoring='r2'))
    known_cv_score = 0.795877470354

    assert np.allclose(known_cv_score, cv_score)


def test_ZeroCount():
    """Assert that ZeroCount operator returns correct transformed X."""
    X = np.array([[0, 1, 7, 0, 0], [3, 0, 0, 2, 19], [0, 1, 3, 4, 5], [5, 0, 0, 0, 0]])
    op = ZeroCount()
    X_transformed = op.transform(X)
    zero_col = np.array([3, 2, 1, 4])
    non_zero = np.array([2, 3, 4, 1])

    assert np.allclose(zero_col, X_transformed[:, 0])
    assert np.allclose(non_zero, X_transformed[:, 1])

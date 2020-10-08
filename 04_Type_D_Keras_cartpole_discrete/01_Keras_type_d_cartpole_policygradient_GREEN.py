import numpy as np
import time, datetime
import gym
import pylab
import sys
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# from collections import deque
from keras.layers import Dense, Input
from keras.optimizers import Adam
from keras import backend as K
from keras.models import Model

import tensorflow as tf

env_name = "CartPole-v1"
# set environment
env = gym.make(env_name)
env.seed(1)     # reproducible, general Policy gradient has high variance
# env = env.unwrapped

# get size of state and action from environment
state_size = env.observation_space.shape[0]
action_size = env.action_space.n

game_name =  sys.argv[0][:-3]

model_path = "save_model/" + game_name
graph_path = "save_graph/" + game_name

# Make folder for save data
if not os.path.exists(model_path):
    os.makedirs(model_path)
if not os.path.exists(graph_path):
    os.makedirs(graph_path)
    
# This is A3C(Asychronous Advantage Actor-Critic) agent for the Cartpole
class RL_Agent:
    def __init__(self, state_size, action_size, env_name):

        # get size of state and action
        self.state_size = state_size
        self.action_size = action_size
        
        # these is hyper parameters for the RL_agent
        self.actor_lr = 0.001
        self.hidden1, self.hidden2 = 64, 64
        
        # train time define
        self.actor = self.build_model()
        self.loss_and_train = self.actor_optimizer()
                
        self.discount_factor = 0.99         # decay rate
        self.buffer_state, self.buffer_action, self.buffer_reward = [], [], []
        self.ep_trial_step = 500
        self.render = False
        self.training_time = 5*60

    # approximate policy and value using Neural Network
    # actor -> state is input and probability of each action is output of network
    def build_model(self):
        state = Input(batch_shape=[None, self.state_size])
        shared = Dense(self.hidden1, input_dim=self.state_size, activation='relu', kernel_initializer='glorot_uniform')(state)

        actor_hidden = Dense(self.hidden2, activation='relu', kernel_initializer='glorot_uniform')(shared)
        actor_predict = Dense(self.action_size, activation='softmax', kernel_initializer='glorot_uniform')(actor_hidden)
        actor = Model(inputs=state, outputs=actor_predict)
        # actor._make_predict_function()
        actor.summary()
        return actor

    # make loss function for Policy Gradient
    # [log(action probability) * q_target] will be input for the back prop
    # we add entropy of action probability to loss
    
    def actor_optimizer(self):
        action = K.placeholder(shape=[None, self.action_size])
        q_target = K.placeholder(shape=[None, ])

        # Policy Gradient 의 핵심
        # log(정책) * return 의 gradient 를 구해서 최대화시킴
        policy = self.actor.output
        log_p = K.sum(action * policy, axis=1)
        log_lik = K.log(log_p + 1e-10) * K.stop_gradient(q_target)
        loss = -K.sum(log_lik)

        entropy = K.sum(policy * K.log(policy + 1e-10), axis=1)

        actor_loss = loss + 0.01*entropy

        # create training function
        optimizer = Adam(lr=self.actor_lr)
        updates = optimizer.get_updates(self.actor.trainable_weights, [], actor_loss)
        train = K.function([self.actor.input, action, q_target], [], updates=updates)
        return train

    # save <s, a ,r> of each step
    # this is used for calculating discounted rewards
    def append_sample(self, state, action, reward):
        
        action_array = np.zeros(self.action_size)
        action_array[action] = 1
        self.buffer_state.append(state[0])
        self.buffer_action.append(action_array)
        self.buffer_reward.append(reward)

    # update policy network and value network every episode
    def train_model(self):
        # discounted_rewards = self.discount_and_norm_rewards(self.buffer_reward)
        
        discounted_rewards = np.zeros_like(self.buffer_reward)
        running_add = 0
        for index in reversed(range(0, len(self.buffer_reward))):
            running_add = running_add * self.discount_factor + self.buffer_reward[index]
            discounted_rewards[index] = running_add
            
        discounted_rewards -= np.mean(discounted_rewards)
        discounted_rewards /= np.std(discounted_rewards)

        self.loss_and_train([self.buffer_state, self.buffer_action, discounted_rewards])
        self.buffer_state, self.buffer_action, self.buffer_reward = [], [], []

    # using the output of policy network, pick action stochastically
    def get_action(self, state):
        # Run forward propagation to get softmax probabilities
        policy = self.actor.predict(state, batch_size=1).flatten()
        # Select action using a biased sample
        # this will return the index of the action we've sampled
        action = np.random.choice(self.action_size, 1, p=policy)[0]
        return action

    def run(self):
        scores, episodes = [], []
        avg_score = 0

        episode = 0
        time_step = 0
        # start training    
        # Step 3.2: run the game
        start_time = time.time()

        while time.time() - start_time < self.training_time and avg_score < 490:
            done = False
            score = 0
            state = env.reset()
            state = np.reshape(state, [1, self.state_size])

            while not done and score < self.ep_trial_step:
                # every time step we do train from the replay memory
                score += 1
                time_step += 1

                # fresh env
                if self.render:
                    env.render()
                
                # Select action_arr
                action = self.get_action(state)

                # run the selected action_arr and observe next state and reward
                next_state, reward, done, _ = env.step(action)
                next_state = np.reshape(next_state, [1, self.state_size])
                
                # It is specific for cartpole.
                if done:
                    reward = -100

                # save the sample <state, action, reward> to the memory
                self.append_sample(state, action, reward)

                # update the old values
                state = next_state

                # train when epsisode finished
                if done or score == self.ep_trial_step:
                    episode += 1
                    self.train_model()

                    # every episode, plot the play time
                    scores.append(score)
                    episodes.append(episode)
                    avg_score = np.mean(scores[-min(30, len(scores)):])
                    print("episode :{:>5d}".format(episode), "/ score :{:>5.0f}".format(score), \
                          "/ last 30 game avg :{:>4.1f}".format(avg_score))

        # pylab.plot(episodes, scores, 'b')
        # pylab.savefig("./save_graph/Cartpole_ActorCritc.png")

        e = int(time.time() - start_time)
        print(' Elasped time :{:02d}:{:02d}:{:02d}'.format(e // 3600, (e % 3600 // 60), e % 60))
        # sys.exit()
        
if __name__ == "__main__":
    global_agent = RL_Agent(state_size, action_size, "network")
    display_time = datetime.datetime.now()
    print("\n\n",game_name, "-game start at :",display_time,"\n")
    
    # if actor exists, restore actor
    if os.path.isfile("./save_model/Cartpole_Actor.h5"):
        global_agent.actor.load_weights("./save_model/Cartpole_Actor.h5")
        print(" Actor restored!!")
        
    global_agent.run()
    
    # Save the trained results
    global_agent.actor.save_weights("./save_model/Cartpole_Actor.h5")

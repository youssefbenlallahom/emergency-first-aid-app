"""
Reinforcement Learning Training System for CPR Coaching
Uses logged CPR sessions to train better feedback responses
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from collections import defaultdict
import pickle

class CPRRewardCalculator:
    """Calculate rewards based on how feedback affected performance"""
    
    def __init__(self):
        self.metric_weights = {
            'overall': 0.30,
            'arm_score': 0.15,
            'depth_score': 0.25,
            'rate_score': 0.20,
            'recoil_score': 0.10
        }
    
    def calculate_improvement(self, before_scores, after_scores, focus_metric):
        """
        Calculate reward based on improvement after feedback
        Positive reward = improvement, Negative = degradation
        """
        # Overall improvement
        overall_delta = after_scores['overall'] - before_scores['overall']
        
        # Focused metric improvement (what feedback targeted)
        if focus_metric and focus_metric in before_scores:
            focused_delta = after_scores.get(focus_metric, 0) - before_scores[focus_metric]
            focused_weight = 2.0  # Extra weight for targeted improvement
        else:
            focused_delta = 0
            focused_weight = 0
        
        # Weighted reward calculation
        reward = (
            overall_delta * self.metric_weights['overall'] +
            focused_delta * focused_weight * 0.15
        )
        
        # Bonus for sustained improvement
        if overall_delta > 10:
            reward += 5
        elif overall_delta > 5:
            reward += 2
        
        # Penalty for degradation
        if overall_delta < -5:
            reward -= 3
        
        return reward
    
    def calculate_long_term_impact(self, window_before, window_after):
        """Calculate sustained improvement over time windows"""
        avg_before = np.mean(window_before)
        avg_after = np.mean(window_after)
        
        stability_before = np.std(window_before)
        stability_after = np.std(window_after)
        
        # Reward both improvement and stability
        improvement_reward = (avg_after - avg_before) * 0.3
        stability_reward = (stability_before - stability_after) * 0.1
        
        return improvement_reward + stability_reward


class FeedbackAnalyzer:
    """Analyze feedback effectiveness from logs"""
    
    def __init__(self, log_file):
        # FIX: Try reading with different common encodings
        try:
            self.df = pd.read_csv(log_file, encoding='utf-8')
        except UnicodeDecodeError:
            print(f"    ⚠️ UTF-8 failed for {log_file}. Trying latin1...")
            self.df = pd.read_csv(log_file, encoding='latin1')
            
        self.feedback_events = []
        self.extract_feedback_events()
    
    def extract_feedback_events(self):
        """Extract all feedback events and their context"""
        feedback_rows = self.df[self.df['feedback_given'].notna() & (self.df['feedback_given'] != '')]
        
        for idx, row in feedback_rows.iterrows():
            event = {
                'timestamp': row['timestamp'],
                'frame': row['frame_number'],
                'feedback': row['feedback_given'],
                'scores_before': self._get_scores_before(idx),
                'scores_after': self._get_scores_after(idx),
                'context': self._get_context(idx)
            }
            self.feedback_events.append(event)
        
        return self.feedback_events
    
    def _get_scores_before(self, idx, window=5):
        """Get average scores before feedback"""
        start = max(0, idx - window)
        window_df = self.df.iloc[start:idx]
        
        if len(window_df) == 0:
            return {}
        
        return {
            'overall': window_df['overall_score'].mean(),
            'arm_score': window_df['arm_score'].mean(),
            'depth_score': window_df['depth_score'].mean(),
            'rate_score': window_df['rate_score'].mean(),
            'recoil_score': window_df['recoil_score'].mean(),
            'hand_position_score': window_df['hand_position_score'].mean()
        }
    
    def _get_scores_after(self, idx, window=10):
        """Get average scores after feedback"""
        end = min(len(self.df), idx + window + 1)
        window_df = self.df.iloc[idx+1:end]
        
        if len(window_df) == 0:
            return {}
        
        return {
            'overall': window_df['overall_score'].mean(),
            'arm_score': window_df['arm_score'].mean(),
            'depth_score': window_df['depth_score'].mean(),
            'rate_score': window_df['rate_score'].mean(),
            'recoil_score': window_df['recoil_score'].mean(),
            'hand_position_score': window_df['hand_position_score'].mean()
        }
    
    def _get_context(self, idx):
        """Get contextual information about the situation"""
        row = self.df.iloc[idx]
        return {
            'fatigue_level': row['fatigue_level'],
            'compression_count': row['compression_count'],
            'rate_cpm': row['rate_cpm'],
            'depth_cm': row['depth_cm']
        }


class RLTrainer:
    """Reinforcement Learning trainer for CPR feedback"""
    
    def __init__(self):
        self.reward_calculator = CPRRewardCalculator()
        self.feedback_templates = defaultdict(list)
        self.template_scores = defaultdict(lambda: {'total_reward': 0, 'count': 0, 'avg_reward': 0})
        self.state_action_values = {}  # Q-table for state-action pairs
    
    def process_log_file(self, log_file):
        """Process a single log file and update learning"""
        print(f"\n📊 Processing: {log_file}")
        
        analyzer = FeedbackAnalyzer(log_file)
        events = analyzer.feedback_events
        
        print(f"   Found {len(events)} feedback events")
        
        for event in events:
            self._learn_from_event(event)
        
        return len(events)
    
    def _learn_from_event(self, event):
        """Learn from a single feedback event"""
        feedback = event['feedback']
        scores_before = event['scores_before']
        scores_after = event['scores_after']
        
        if not scores_before or not scores_after:
            return
        
        # Identify focus area from feedback text
        focus_metric = self._identify_focus_metric(feedback)
        
        # Calculate reward
        reward = self.reward_calculator.calculate_improvement(
            scores_before, 
            scores_after, 
            focus_metric
        )
        
        # Create state representation
        state = self._create_state(scores_before, event['context'])
        
        # Update template scores
        template_key = self._generalize_feedback(feedback, focus_metric)
        self.feedback_templates[focus_metric].append(feedback)
        
        scores = self.template_scores[template_key]
        scores['total_reward'] += reward
        scores['count'] += 1
        scores['avg_reward'] = scores['total_reward'] / scores['count']
        
        # Update Q-values
        state_action_key = (state, template_key)
        if state_action_key not in self.state_action_values:
            self.state_action_values[state_action_key] = 0
        
        # Q-learning update: Q(s,a) = Q(s,a) + α * (reward - Q(s,a))
        alpha = 0.1  # Learning rate
        old_value = self.state_action_values[state_action_key]
        self.state_action_values[state_action_key] = old_value + alpha * (reward - old_value)
    
    def _identify_focus_metric(self, feedback):
        """Identify which metric the feedback targets"""
        feedback_lower = feedback.lower()
        
        if any(word in feedback_lower for word in ['arm', 'elbow', 'straight', 'lock']):
            return 'arm_score'
        elif any(word in feedback_lower for word in ['speed', 'rate', 'faster', 'slower', 'per minute']):
            return 'rate_score'
        elif any(word in feedback_lower for word in ['depth', 'deeper', 'push', 'cm', 'centimeter']):
            return 'depth_score'
        elif any(word in feedback_lower for word in ['recoil', 'release', 'chest', 'fully']):
            return 'recoil_score'
        elif any(word in feedback_lower for word in ['hand', 'position', 'center', 'sternum']):
            return 'hand_position_score'
        
        return 'overall'
    
    def _generalize_feedback(self, feedback, focus_metric):
        """Create a generalized template from specific feedback"""
        return f"{focus_metric}_{len(feedback.split())}_words"
    
    def _create_state(self, scores, context):
        """Create discrete state representation"""
        # Discretize scores into bins
        overall_bin = 'high' if scores.get('overall', 0) >= 70 else 'medium' if scores.get('overall', 0) >= 50 else 'low'
        
        worst_metric = min(scores.items(), key=lambda x: x[1])[0] if scores else 'none'
        
        fatigue = 'high' if context.get('fatigue_level', 0) > 50 else 'low'
        
        return f"{overall_bin}_{worst_metric}_{fatigue}"
    
    def get_best_feedback_for_state(self, scores, context):
        """Get best feedback based on learned Q-values"""
        state = self._create_state(scores, context)
        
        # Find best action for this state
        best_action = None
        best_value = float('-inf')
        
        for (s, a), value in self.state_action_values.items():
            if s == state and value > best_value:
                best_value = value
                best_action = a
        
        return best_action, best_value
    
    def get_top_feedback_templates(self, n=10):
        """Get top performing feedback templates"""
        sorted_templates = sorted(
            self.template_scores.items(),
            key=lambda x: x[1]['avg_reward'],
            reverse=True
        )
        return sorted_templates[:n]
    
    def save_model(self, filepath):
        """Save trained model"""
        model_data = {
            'template_scores': dict(self.template_scores),
            'state_action_values': self.state_action_values,
            'feedback_templates': dict(self.feedback_templates),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"✅ Model saved to: {filepath}")
    
    def load_model(self, filepath):
        """Load trained model"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.template_scores = defaultdict(lambda: {'total_reward': 0, 'count': 0, 'avg_reward': 0}, 
                                          model_data['template_scores'])
        self.state_action_values = model_data['state_action_values']
        self.feedback_templates = defaultdict(list, model_data['feedback_templates'])
        
        print(f"✅ Model loaded from: {filepath}")


def train_on_all_logs(logs_directory='cpr_logs'):
    """Train on all available CPR logs"""
    print("🤖 Starting Reinforcement Learning Training")
    print("=" * 60)
    
    trainer = RLTrainer()
    
    # Find all log files
    log_files = [f for f in os.listdir(logs_directory) if f.endswith('.csv')]
    
    if not log_files:
        print(f"❌ No log files found in {logs_directory}")
        return None
    
    print(f"📁 Found {len(log_files)} log files\n")
    
    total_events = 0
    for log_file in log_files:
        filepath = os.path.join(logs_directory, log_file)
        events = trainer.process_log_file(filepath)
        total_events += events
    
    print("\n" + "=" * 60)
    print(f"✅ Training Complete!")
    print(f"   Total feedback events analyzed: {total_events}")
    print(f"   Unique states learned: {len(set(k[0] for k in trainer.state_action_values.keys()))}")
    print(f"   Total state-action pairs: {len(trainer.state_action_values)}")
    
    # Show top feedback templates
    print("\n📈 Top 10 Most Effective Feedback Templates:")
    print("-" * 60)
    top_templates = trainer.get_top_feedback_templates(10)
    
    for i, (template, scores) in enumerate(top_templates, 1):
        print(f"{i}. {template}")
        print(f"   Avg Reward: {scores['avg_reward']:.2f} (used {scores['count']} times)")
    
    # Save model
    model_path = 'cpr_rl_model.pkl'
    trainer.save_model(model_path)
    
    return trainer


def generate_improved_coaching_prompts(trainer):
    """Generate improved coaching prompts based on RL learning"""
    
    print("\n" + "=" * 60)
    print("🎯 Generating Improved Coaching Prompts")
    print("=" * 60)
    
    # Analyze what worked best for each metric
    metric_best_practices = {}
    
    for metric in ['arm_score', 'rate_score', 'depth_score', 'recoil_score', 'hand_position_score']:
        # Find best performing templates for this metric
        metric_templates = [(k, v) for k, v in trainer.template_scores.items() 
                          if metric in k and v['count'] >= 2]
        
        if metric_templates:
            best = max(metric_templates, key=lambda x: x[1]['avg_reward'])
            metric_best_practices[metric] = {
                'template': best[0],
                'avg_reward': best[1]['avg_reward'],
                'sample_feedback': trainer.feedback_templates.get(metric, ['No samples'])[:3]
            }
    
    # Generate recommendations
    recommendations = {
        'prompt_improvements': {},
        'timing_suggestions': {},
        'metric_priorities': {}
    }
    
    for metric, data in metric_best_practices.items():
        print(f"\n✨ {metric.replace('_', ' ').title()}:")
        print(f"   Best approach reward: {data['avg_reward']:.2f}")
        print(f"   Sample effective feedback:")
        for sample in data['sample_feedback'][:2]:
            print(f"   - {sample}")
        
        recommendations['prompt_improvements'][metric] = {
            'focus': 'Use concise, actionable language' if data['avg_reward'] > 0 else 'Needs more specific guidance',
            'samples': data['sample_feedback']
        }
    
    return recommendations


def export_training_results(trainer, output_file='rl_training_results.json'):
    """Export training results for integration with main system"""
    
    results = {
        'metadata': {
            'training_date': datetime.now().isoformat(),
            'total_states': len(set(k[0] for k in trainer.state_action_values.keys())),
            'total_actions': len(trainer.template_scores)
        },
        'best_actions_per_state': {},
        'feedback_effectiveness': {},
        'recommendations': {}
    }
    
    # Export best action for each state
    states = set(k[0] for k in trainer.state_action_values.keys())
    
    for state in states:
        state_actions = [(k[1], v) for k, v in trainer.state_action_values.items() if k[0] == state]
        if state_actions:
            best_action, best_value = max(state_actions, key=lambda x: x[1])
            results['best_actions_per_state'][state] = {
                'action': best_action,
                'expected_value': float(best_value)
            }
    
    # Export feedback effectiveness
    for template, scores in trainer.template_scores.items():
        results['feedback_effectiveness'][template] = {
            'avg_reward': float(scores['avg_reward']),
            'usage_count': scores['count']
        }
    
    # Save to JSON
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results exported to: {output_file}")
    return results


if __name__ == "__main__":
    # Train on all available logs
    trainer = train_on_all_logs('cpr_logs')
    
    if trainer:
        # Generate improved prompts
        recommendations = generate_improved_coaching_prompts(trainer)
        
        # Export results
        export_training_results(trainer)
        
        
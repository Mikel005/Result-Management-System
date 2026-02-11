"""
AI Engine for Result Management System
Provides intelligent features like predictions, insights, and recommendations
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression # type: ignore
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import sqlite3
from datetime import datetime
import json
from utils import calculate_grade

class AIEngine:
    def __init__(self, db_path='results.db'):
        self.db_path = db_path
        
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def predict_performance(self, student_id):
        """Predict student's future performance based on past results"""
        conn = self.get_connection()
        
        # Get student's historical results
        query = """
        SELECT r.marks, r.subject_code, r.created_at,
            s.subject_name
        FROM results r
        JOIN subjects s ON r.subject_code = s.subject_code
        WHERE r.student_id = ? AND r.status = 'approved'
        ORDER BY r.created_at
        """
        
        df = pd.read_sql_query(query, conn, params=(student_id,))
        conn.close()
        
        if len(df) < 2:
            return {
                'prediction': None,
                'message': 'Not enough data for prediction (minimum 2 results needed)'
            }
        
        # Create features for prediction
        df['result_number'] = range(1, len(df) + 1)
        
        predictions = {}
        
        # Predict for each subject
        for subject in df['subject_code'].unique():
            subject_data = df[df['subject_code'] == subject].copy()
            
            if len(subject_data) >= 2:
                X = subject_data[['result_number']].values
                y = subject_data['marks'].values
                
                model = LinearRegression()
                model.fit(X, y)
                
                # Predict next performance
                next_result_num = len(subject_data) + 1
                predicted_marks = model.predict([[next_result_num]])[0]
                predicted_marks = max(0, min(100, predicted_marks))  # Clamp to 0-100
                
                # Calculate trend
                if len(subject_data) >= 2:
                    recent_avg = subject_data.tail(2)['marks'].mean()
                    overall_avg = subject_data['marks'].mean()
                    trend = 'improving' if recent_avg > overall_avg else 'declining' if recent_avg < overall_avg else 'stable'
                else:
                    trend = 'stable'
                
                predictions[subject_data.iloc[0]['subject_name']] = {
                    'predicted_marks': round(predicted_marks, 2),
                    'current_average': round(subject_data['marks'].mean(), 2),
                    'trend': trend,
                    'confidence': 'high' if len(subject_data) >= 4 else 'medium' if len(subject_data) >= 2 else 'low'
                }
        
        return {
            'prediction': predictions,
            'overall_trend': self._calculate_overall_trend(df),
            'message': 'Predictions generated successfully'
        }
    
    def _calculate_overall_trend(self, df):
        """Calculate overall performance trend"""
        if len(df) < 2:
            return 'insufficient_data'
        
        recent_marks = df.tail(int(len(df)/2))['marks'].mean()
        earlier_marks = df.head(int(len(df)/2))['marks'].mean()
        
        if recent_marks > earlier_marks + 5:
            return 'strongly_improving'
        elif recent_marks > earlier_marks:
            return 'improving'
        elif recent_marks < earlier_marks - 5:
            return 'strongly_declining'
        elif recent_marks < earlier_marks:
            return 'declining'
        else:
            return 'stable'
    
    def identify_at_risk_students(self, threshold=60):
        """Identify students at risk of failing"""
        conn = self.get_connection()
        
        query = """
        SELECT s.student_id, s.name, s.class,
            AVG(r.marks) as avg_marks,
            COUNT(r.id) as total_results,
            SUM(CASE WHEN r.marks < ? THEN 1 ELSE 0 END) as failing_count
        FROM students s
        LEFT JOIN results r ON s.student_id = r.student_id AND r.status = 'approved'
        GROUP BY s.student_id, s.name, s.class
        HAVING avg_marks < ? OR failing_count > 0
        ORDER BY avg_marks ASC
        """
        
        df = pd.read_sql_query(query, conn, params=(threshold, threshold))
        conn.close()
        
        at_risk = []
        for _, row in df.iterrows():
            risk_level = 'high' if row['avg_marks'] < 50 else 'medium' if row['avg_marks'] < threshold else 'low'
            at_risk.append({
                'student_id': row['student_id'],
                'name': row['name'],
                'class': row['class'],
                'average_marks': round(row['avg_marks'], 2) if row['avg_marks'] else 0,
                'total_results': int(row['total_results']) if row['total_results'] else 0,
                'failing_subjects': int(row['failing_count']) if row['failing_count'] else 0,
                'risk_level': risk_level
            })
        
        return at_risk
    
    def generate_personalized_recommendations(self, student_id):
        """Generate AI-powered recommendations for student improvement"""
        conn = self.get_connection()
        
        # Get student performance by subject
        query = """
        SELECT r.subject_code, sub.subject_name, 
            AVG(r.marks) as avg_marks,
            COUNT(r.id) as total_exams,
            MAX(r.marks) as best_marks,
            MIN(r.marks) as worst_marks
        FROM results r
        JOIN subjects sub ON r.subject_code = sub.subject_code
        WHERE r.student_id = ? AND r.status = 'approved'
        GROUP BY r.subject_code, sub.subject_name
        """
        
        df = pd.read_sql_query(query, conn, params=(student_id,))
        conn.close()
        
        if df.empty:
            return {
                'recommendations': [],
                'message': 'No results found for this student'
            }
        
        recommendations = []
        
        for _, row in df.iterrows():
            avg = row['avg_marks']
            subject = row['subject_name']
            
            if avg < 50:
                priority = 'critical'
                advice = f"Requires immediate attention in {subject}. Consider extra tutoring and practice."
            elif avg < 60:
                priority = 'high'
                advice = f"Focus on improving {subject} fundamentals. Regular practice recommended."
            elif avg < 75:
                priority = 'medium'
                advice = f"Good progress in {subject}. Work on advanced topics for better grades."
            else:
                priority = 'low'
                advice = f"Excellent performance in {subject}. Maintain consistency and challenge yourself."
            
            # Check consistency
            variance = row['best_marks'] - row['worst_marks']
            if variance > 30:
                consistency_note = f"Performance varies significantly (range: {variance:.1f}). Work on maintaining consistency."
            else:
                consistency_note = "Performance is consistent. Keep up the good work!"
            
            recommendations.append({
                'subject': subject,
                'average': round(avg, 2),
                'priority': priority,
                'advice': advice,
                'consistency': consistency_note,
                'best_score': round(row['best_marks'], 2),
                'improvement_potential': round(100 - avg, 2)
            })
        
        # Sort by priority
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        recommendations.sort(key=lambda x: priority_order[x['priority']])
        
        return {
            'recommendations': recommendations,
            'overall_average': round(df['avg_marks'].mean(), 2),
            'message': 'Recommendations generated successfully'
        }
    
    def detect_anomalies(self):
        """Detect unusual patterns in results (potential cheating or data errors)"""
        conn = self.get_connection()
        
        query = """
        SELECT r.id, r.student_id, s.name, r.subject_code, sub.subject_name,
            r.marks, r.created_at
        FROM results r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_code = sub.subject_code
        WHERE r.status = 'approved'
        ORDER BY r.student_id, r.created_at
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        anomalies = []
        
        # Check for sudden large improvements
        for student in df['student_id'].unique():
            student_data = df[df['student_id'] == student].sort_values('created_at')
            
            if len(student_data) < 2:
                continue
            
            for i in range(1, len(student_data)):
                current = student_data.iloc[i]
                previous = student_data.iloc[i-1]
                
                marks_increase = current['marks'] - previous['marks']
                
                # Flag large sudden improvements (>40 marks)
                if marks_increase > 40:
                    anomalies.append({
                        'type': 'sudden_improvement',
                        'student_id': current['student_id'],
                        'student_name': current['name'],
                        'subject': current['subject_name'],
                        'previous_marks': round(previous['marks'], 2),
                        'current_marks': round(current['marks'], 2),
                        'increase': round(marks_increase, 2),
                        'severity': 'high' if marks_increase > 50 else 'medium',
                        'date': current['created_at']
                    })
        
        # Check for perfect scores across multiple subjects (rare)
        perfect_scores = df[df['marks'] >= 99].groupby('student_id').size()
        for student_id, count in perfect_scores.items():
            if count >= 3:
                student_name = df[df['student_id'] == student_id].iloc[0]['name']
                anomalies.append({
                    'type': 'multiple_perfect_scores',
                    'student_id': student_id,
                    'student_name': student_name,
                    'count': int(count),
                    'severity': 'low',
                    'note': 'Exceptional performance - verify if genuine'
                })
        
        return anomalies
    
    def get_comparative_insights(self, student_id):
        """Compare student performance with class and overall averages"""
        conn = self.get_connection()
        
        # Get student's class
        student_query = "SELECT class FROM students WHERE student_id = ?"
        student_class = pd.read_sql_query(student_query, conn, params=(student_id,))
        
        if student_class.empty:
            conn.close()
            return {'message': 'Student not found'}
        
        student_class = student_class.iloc[0]['class']
        
        # Get comprehensive comparison data
        query = """
        SELECT 
            r.subject_code,
            sub.subject_name,
            AVG(CASE WHEN r.student_id = ? THEN r.marks END) as student_avg,
            AVG(CASE WHEN s.class = ? THEN r.marks END) as class_avg,
            AVG(r.marks) as overall_avg,
            MAX(r.marks) as highest_marks,
            MIN(r.marks) as lowest_marks
        FROM results r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_code = sub.subject_code
        WHERE r.status = 'approved'
        GROUP BY r.subject_code, sub.subject_name
        """
        
        df = pd.read_sql_query(query, conn, params=(student_id, student_class))
        conn.close()
        
        insights = []
        for _, row in df.iterrows():
            student_avg = row['student_avg']
            class_avg = row['class_avg']
            overall_avg = row['overall_avg']
            
            if student_avg is None:
                continue
            
            # Calculate percentile
            class_percentile = ((student_avg - row['lowest_marks']) / (row['highest_marks'] - row['lowest_marks']) * 100) if row['highest_marks'] != row['lowest_marks'] else 50
            
            # Determine standing
            if student_avg >= class_avg + 10:
                standing = 'excellent'
            elif student_avg >= class_avg:
                standing = 'above_average'
            elif student_avg >= class_avg - 10:
                standing = 'average'
            else:
                standing = 'below_average'
            
            insights.append({
                'subject': row['subject_name'],
                'student_average': round(student_avg, 2),
                'class_average': round(class_avg, 2),
                'overall_average': round(overall_avg, 2),
                'difference_from_class': round(student_avg - class_avg, 2),
                'percentile': round(class_percentile, 1),
                'standing': standing,
                'class_rank_estimate': self._estimate_rank(student_avg, class_avg, standing)
            })
        
        return {
            'insights': insights,
            'student_class': student_class,
            'message': 'Comparative analysis completed'
        }
    
    def _estimate_rank(self, student_avg, class_avg, standing):
        """Estimate class rank based on performance"""
        if standing == 'excellent':
            return 'Top 10%'
        elif standing == 'above_average':
            return 'Top 25%'
        elif standing == 'average':
            return 'Top 50%'
        else:
            return 'Bottom 50%'
    
    def predict_final_grade(self, student_id, subject_code):
        """Predict final grade based on partial results"""
        conn = self.get_connection()
        
        query = """
        SELECT marks, created_at
        FROM results
        WHERE student_id = ? AND subject_code = ? AND status = 'approved'
        ORDER BY created_at
        """
        
        df = pd.read_sql_query(query, conn, params=(student_id, subject_code))
        conn.close()
        
        if len(df) < 2:
            return {
                'predicted_grade': None,
                'message': 'Not enough data for prediction'
            }
        
        # Calculate weighted average (recent results weighted more)
        weights = np.linspace(0.5, 1.5, len(df))
        weighted_avg = np.average(df['marks'], weights=weights)
        
        # Predict with trend
        trend = df['marks'].iloc[-1] - df['marks'].iloc[0]
        predicted_marks = weighted_avg + (trend * 0.2)  # Factor in trend
        predicted_marks = max(0, min(100, predicted_marks))
        
        # Determine grade
        grade = calculate_grade(predicted_marks)
        
        return {
            'predicted_marks': round(predicted_marks, 2),
            'predicted_grade': grade,
            'current_average': round(df['marks'].mean(), 2),
            'trend': 'positive' if trend > 0 else 'negative' if trend < 0 else 'stable',
            'confidence': 'high' if len(df) >= 4 else 'medium',
            'message': 'Prediction completed'
        }
    
    def generate_class_insights(self, class_name):
        """Generate AI insights for entire class"""
        conn = self.get_connection()
        
        query = """
        SELECT s.student_id, s.name, 
            AVG(r.marks) as avg_marks,
            COUNT(DISTINCT r.subject_code) as subjects_taken,
            SUM(CASE WHEN r.grade IN ('A') THEN 1 ELSE 0 END) as excellent_count,
            SUM(CASE WHEN r.marks < 50 THEN 1 ELSE 0 END) as failing_count
        FROM students s
        LEFT JOIN results r ON s.student_id = r.student_id AND r.status = 'approved'
        WHERE s.class = ?
        GROUP BY s.student_id, s.name
        """
        
        df = pd.read_sql_query(query, conn, params=(class_name,))
        conn.close()
        
        if df.empty:
            return {'message': 'No data found for this class'}
        
        # Calculate class statistics
        class_avg = df['avg_marks'].mean()
        top_performers = df.nlargest(3, 'avg_marks')[['name', 'avg_marks']].to_dict('records')
        needs_attention = df[df['avg_marks'] < 60][['name', 'avg_marks', 'failing_count']].to_dict('records')
        
        # Performance distribution
        excellent = len(df[df['avg_marks'] >= 85])
        good = len(df[(df['avg_marks'] >= 70) & (df['avg_marks'] < 85)])
        average = len(df[(df['avg_marks'] >= 50) & (df['avg_marks'] < 70)])
        poor = len(df[df['avg_marks'] < 50])
        
        return {
            'class_name': class_name,
            'total_students': len(df),
            'class_average': round(class_avg, 2),
            'top_performers': [{'name': p['name'], 'average': round(p['avg_marks'], 2)} for p in top_performers],
            'students_needing_attention': [{'name': s['name'], 'average': round(s['avg_marks'], 2), 'failing': int(s['failing_count'])} for s in needs_attention],
            'performance_distribution': {
                'excellent': excellent,
                'good': good,
                'average': average,
                'poor': poor
            },
            'pass_rate': round((len(df[df['avg_marks'] >= 50]) / len(df) * 100), 2) if len(df) > 0 else 0,
            'message': 'Class insights generated successfully'
        }
    
    def smart_grade_suggestion(self, student_id, subject_code, current_marks):
        """Suggest if current marks align with student's typical performance"""
        conn = self.get_connection()
        
        query = """
        SELECT marks FROM results
        WHERE student_id = ? AND subject_code = ? AND status = 'approved'
        """
        
        df = pd.read_sql_query(query, conn, params=(student_id, subject_code))
        conn.close()
        
        if df.empty:
            return {
                'suggestion': 'accept',
                'reason': 'No historical data available',
                'confidence': 'low'
            }
        
        mean = df['marks'].mean()
        std = df['marks'].std()
        
        # Check if current marks are within 2 standard deviations
        if abs(current_marks - mean) > 2 * std:
            if current_marks > mean:
                suggestion = 'verify'
                reason = f'Marks significantly higher than usual (typical: {mean:.1f}±{std:.1f})'
            else:
                suggestion = 'verify'
                reason = f'Marks significantly lower than usual (typical: {mean:.1f}±{std:.1f})'
            confidence = 'high'
        elif abs(current_marks - mean) > std:
            suggestion = 'review'
            reason = f'Marks somewhat different from typical performance (usual: {mean:.1f}±{std:.1f})'
            confidence = 'medium'
        else:
            suggestion = 'accept'
            reason = f'Marks align with typical performance (usual: {mean:.1f}±{std:.1f})'
            confidence = 'high'
        
        return {
            'suggestion': suggestion,
            'reason': reason,
            'confidence': confidence,
            'typical_average': round(mean, 2),
            'standard_deviation': round(std, 2)
        }
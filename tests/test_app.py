#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes para o sistema PortoEx
"""

import unittest
import json
from improved_chico_automate_fpdf import app

class PortoExTestCase(unittest.TestCase):
    
    def setUp(self):
        """Configuração dos testes"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_login_page(self):
        """Teste da página de login"""
        result = self.app.get('/login')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'login', result.data.lower())
    
    def test_redirect_when_not_logged(self):
        """Teste de redirecionamento quando não logado"""
        result = self.app.get('/')
        self.assertEqual(result.status_code, 302)  # Redirect para login
    
    def test_login_success(self):
        """Teste de login com sucesso"""
        result = self.app.post('/login', 
                              data=json.dumps({
                                  'usuario': 'comercial.ptx',
                                  'senha': 'ptx@123'
                              }),
                              content_type='application/json')
        data = json.loads(result.data)
        self.assertTrue(data['success'])
    
    def test_login_failure(self):
        """Teste de login com falha"""
        result = self.app.post('/login',
                              data=json.dumps({
                                  'usuario': 'user_invalid',
                                  'senha': 'wrong_password'
                              }),
                              content_type='application/json')
        self.assertEqual(result.status_code, 401)
    
    def test_estados_endpoint(self):
        """Teste do endpoint de estados"""
        # Primeiro fazer login
        self.app.post('/login',
                     data=json.dumps({
                         'usuario': 'comercial.ptx',
                         'senha': 'ptx@123'
                     }),
                     content_type='application/json')
        
        result = self.app.get('/estados')
        self.assertEqual(result.status_code, 200)
        data = json.loads(result.data)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

if __name__ == '__main__':
    unittest.main() 
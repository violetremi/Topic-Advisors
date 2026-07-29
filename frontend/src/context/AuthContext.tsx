/** 轻量鉴权上下文：用户名即身份，无密码。
 *  - 登录成功后写入 localStorage 并广播 username
 *  - 监听 intel:unauthorized 事件（任意接口返回 401 时），自动登出
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import {
  getStoredUsername,
  setStoredUsername,
  clearStoredUsername,
  login as apiLogin,
} from '../api';

interface AuthContextValue {
  username: string | null;
  login: (username: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(() => getStoredUsername());

  useEffect(() => {
    const handler = () => setUsername(null);
    window.addEventListener('intel:unauthorized', handler);
    return () => window.removeEventListener('intel:unauthorized', handler);
  }, []);

  const login = useCallback(async (rawName: string) => {
    const name = (rawName || '').trim();
    if (!name) {
      throw new Error('请输入用户名');
    }
    // 后端用户名不存在则自动创建（占用即登录已有账号）
    await apiLogin(name);
    setStoredUsername(name);
    setUsername(name);
  }, []);

  const logout = useCallback(() => {
    clearStoredUsername();
    setUsername(null);
  }, []);

  return (
    <AuthContext.Provider value={{ username, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth 必须在 AuthProvider 内使用');
  }
  return ctx;
}

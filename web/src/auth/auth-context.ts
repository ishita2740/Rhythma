import { createContext } from 'react';

export interface User {
  id: string;
  username: string;
  email: string;
  role?: string;
  full_name?: string | null;
  specialty?: string | null;
}

export interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    fullName?: string,
    role?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => Promise<void>;
  loginProvider: (email: string, password: string) => Promise<void>;
  registerProvider: (
    email: string,
    password: string,
    fullName?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => Promise<void>;
  logout: (redirectTo?: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock window.confirm
window.confirm = vi.fn(() => true);

// Mock global fetch
global.fetch = vi.fn();

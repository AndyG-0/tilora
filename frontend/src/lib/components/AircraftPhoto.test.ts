import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import AircraftPhoto from './AircraftPhoto.svelte';

describe('AircraftPhoto', () => {
	it('renders placeholder with kind icon when no src is provided', () => {
		const { container } = render(AircraftPhoto, {
			props: { src: null, kind: 'jet', size: 'md' },
		});

		expect(container.querySelector('.placeholder')).toBeInTheDocument();
		expect(container.querySelector('img.photo')).toBeNull();
	});

	it('renders image when src is provided', () => {
		const { container } = render(AircraftPhoto, {
			props: {
				src: 'https://example.com/aircraft.jpg',
				alt: 'Boeing 737',
				kind: 'jet',
				size: 'md',
				photographer: 'John Spotter',
			},
		});

		const img = container.querySelector('img.photo');
		expect(img).toBeInTheDocument();
		expect(img).toHaveAttribute('src', 'https://example.com/aircraft.jpg');
		expect(screen.getByText('© John Spotter')).toBeInTheDocument();
	});

	it('renders photographer link when link prop is provided', () => {
		render(AircraftPhoto, {
			props: {
				src: 'https://example.com/aircraft.jpg',
				photographer: 'Jane Doe',
				link: 'https://planespotters.net/photo/12345',
				size: 'md',
			},
		});

		const link = screen.getByRole('link', { name: '© Jane Doe' });
		expect(link).toHaveAttribute('href', 'https://planespotters.net/photo/12345');
		expect(link).toHaveAttribute('target', '_blank');
	});
});

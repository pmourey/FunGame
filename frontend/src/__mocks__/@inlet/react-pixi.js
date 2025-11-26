import React from 'react'

export const Stage = ({children, ...props}) => <div data-testid="pixi-stage">{children}</div>
export const Container = ({children}) => <div data-testid="pixi-container">{children}</div>
export const Sprite = ({x, y, width, height}) => <div data-testid="pixi-sprite" style={{position:'absolute', left: x, top: y, width, height}} />
export const Graphics = () => <div />
export const Text = ({children}) => <div>{children}</div>

export default {Stage, Container, Sprite, Graphics, Text}

